import os
import tempfile
import cv2
from flask import Flask, request, render_template, redirect
from werkzeug.utils import secure_filename
from evaluator import evaluate_screenshot
from modules.video_frame_extractor import extract_frames
from dotenv import load_dotenv
from supabase import create_client, Client
import json

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

# Use /tmp for serverless environments (Vercel, AWS Lambda, etc.)
# Falls back to local 'uploads' for local development
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'skillblade_uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit for videos

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'mp4', 'webm', 'avi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_files(filepaths):
    """Remove uploaded/temp files after processing to avoid filling /tmp."""
    for fp in filepaths:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except OSError:
            pass

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        mode = request.form.get('upload_mode', 'images')
        
        if 'files' not in request.files:
            return redirect(request.url)
        
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return redirect(request.url)
            
        filepaths = []
        video_meta = None
        
        if mode == 'video':
            # Handle single video
            file = files[0]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(video_path)
                
                # Extract frames
                try:
                    frames, video_meta = extract_frames(video_path, target_fps=1.0, max_frames=20)
                    for i, frame in enumerate(frames):
                        frame_filename = f"frame_{i:03d}_{filename}.jpg"
                        frame_path = os.path.join(app.config['UPLOAD_FOLDER'], frame_filename)
                        cv2.imwrite(frame_path, frame)
                        filepaths.append(frame_path)
                    
                    # Clean up the original video to save space
                    os.remove(video_path)
                except Exception as e:
                    cleanup_files(filepaths)
                    return render_template('result.html', results={"error": f"Failed to process video: {str(e)}"})
        else:
            # Handle multiple images
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    filepaths.append(filepath)
        
        if not filepaths:
            return render_template('result.html', results={"error": "No valid files were processed."})

        # Evaluate all screenshots/frames
        all_results = []
        for fp in filepaths:
            res = evaluate_screenshot(fp)
            if "error" not in res:
                all_results.append(res)
        
        # Clean up temp files after evaluation
        cleanup_files(filepaths)

        if not all_results:
            return render_template('result.html', results={"error": "Evaluation failed on all files."})
            
        is_multi = len(all_results) > 1

        if is_multi:
            # Aggregate scores (average)
            total_score = sum(r['design_craft_score'] for r in all_results)
            avg_score = round(total_score / len(all_results), 1)
            
            from evaluator import get_tier, tier_description, MAX_POINTS
            tier_name, tier_icon, tier_key = get_tier(avg_score)
            avg_points = round((avg_score / 100) * MAX_POINTS, 1)
            
            aggregated_results = {
                "is_multi": True,
                "mode": mode,
                "file_count": len(filepaths),
                "video_meta": video_meta,
                "design_craft_score": avg_score,
                "design_craft_points": avg_points,
                "max_points": MAX_POINTS,
                "tier_name": tier_name,
                "tier_icon": tier_icon,
                "tier_key": tier_key,
                "tier_desc": tier_description(tier_name),
                "frames": all_results
            }
        else:
            aggregated_results = all_results[0]
            aggregated_results["is_multi"] = False
            aggregated_results["mode"] = mode
            aggregated_results["file_count"] = 1
            
        # Store in Supabase if configured
        if supabase:
            try:
                # Ensure JSON serialization handles numpy types if any leak through, although the evaluator should return standard types
                # We can dump and load to be safe, or just insert the dict directly if standard
                
                db_record = {
                    "mode": mode,
                    "file_count": aggregated_results.get("file_count", 1),
                    "design_craft_score": aggregated_results.get("design_craft_score", 0),
                    "tier_name": aggregated_results.get("tier_name", "Unknown"),
                    "results_json": aggregated_results
                }
                supabase.table("evaluations").insert(db_record).execute()
            except Exception as e:
                print(f"Failed to store result in Supabase: {e}")
            
        return render_template('result.html', results=aggregated_results)
            
    return render_template('index.html')

# Vercel uses this as the WSGI application object
# The variable name 'app' is what @vercel/python looks for by default
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
