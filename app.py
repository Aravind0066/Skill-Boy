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
import uuid

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

        eval_id = str(uuid.uuid4())
        image_urls = []

        if supabase:
            for fp in filepaths:
                try:
                    filename = os.path.basename(fp)
                    storage_path = f"{eval_id}/{filename}"
                    with open(fp, "rb") as f:
                        # Depending on the supabase python client version, upload takes bytes or a file-like object
                        # We will read as bytes
                        file_bytes = f.read()
                        
                        # Specify content-type based on extension
                        content_type = "image/jpeg"
                        if filename.lower().endswith(".png"): content_type = "image/png"
                        elif filename.lower().endswith(".webp"): content_type = "image/webp"
                        
                        supabase.storage.from_("uploads").upload(
                            path=storage_path,
                            file=file_bytes,
                            file_options={"content-type": content_type}
                        )
                    # get public URL
                    public_url = supabase.storage.from_("uploads").get_public_url(storage_path)
                    image_urls.append(public_url)
                except Exception as e:
                    print(f"Supabase upload error for {fp}: {e}")

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
                "file_count": len(all_results),
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
                # Round-trip through JSON to convert any numpy types to native Python
                # NOTE: Keep results_json clean — don't inject id/image_urls into it
                safe_results = json.loads(json.dumps(aggregated_results, default=str))
                
                db_record = {
                    "id": eval_id,
                    "mode": mode,
                    "file_count": int(safe_results.get("file_count", 1)),
                    "design_craft_score": float(safe_results.get("design_craft_score", 0)),
                    "tier_name": str(safe_results.get("tier_name", "Unknown")),
                    "tier_key": str(safe_results.get("tier_key", "unknown")),
                    "tier_icon": str(safe_results.get("tier_icon", "")),
                    "image_urls": image_urls,
                    "results_json": safe_results
                }
                supabase.table("evaluations").insert(db_record).execute()
            except Exception as e:
                print(f"Failed to store result in Supabase: {e}")

        # Attach eval metadata for the result page (after DB write, so results_json stays clean)
        aggregated_results["id"] = eval_id
        aggregated_results["image_urls"] = image_urls

        return render_template('result.html', results=aggregated_results)
            
    return render_template('index.html')

@app.route('/history')
def history():
    if not supabase:
        return render_template('history.html', error="Database not configured. Add SUPABASE_URL and SUPABASE_KEY to your environment variables.", evaluations=[])

    try:
        response = supabase.table('evaluations').select(
            'id, created_at, mode, file_count, design_craft_score, tier_name, tier_key, tier_icon, image_urls'
        ).order('created_at', desc=True).execute()

        evaluations = response.data or []

        # Ensure every record has a safe created_at string for the template's [:10] slice
        for ev in evaluations:
            if not ev.get('created_at'):
                ev['created_at'] = 'Unknown date'
            # Normalise image_urls — Supabase may return None instead of []
            if ev.get('image_urls') is None:
                ev['image_urls'] = []

        return render_template('history.html', evaluations=evaluations, error=None)
    except Exception as e:
        print(f"History fetch error: {e}")
        return render_template('history.html', error=f"Failed to fetch history: {str(e)}", evaluations=[])

@app.route('/history/<string:eval_id>')
def history_detail(eval_id):
    """Show full result page for a previously-evaluated entry.
    
    Uses <string:eval_id> instead of <uuid:eval_id> to avoid Flask rejecting
    IDs that may have been stored with non-standard formatting.
    """
    if not supabase:
        return render_template('history.html', error="Database not configured.", evaluations=[])

    try:
        response = supabase.table('evaluations').select('results_json, image_urls').eq('id', eval_id).execute()
        if not response.data:
            return render_template('history.html', error=f"Evaluation '{eval_id}' not found.", evaluations=[])

        row = response.data[0]
        results = row.get('results_json') or {}

        # Re-attach image_urls so the result page can display thumbnails
        if not results.get('image_urls'):
            results['image_urls'] = row.get('image_urls') or []

        return render_template('result.html', results=results)
    except Exception as e:
        print(f"History detail error for {eval_id}: {e}")
        return render_template('history.html', error=f"Failed to load evaluation: {str(e)}", evaluations=[])


# Vercel uses this as the WSGI application object
# The variable name 'app' is what @vercel/python looks for by default
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
