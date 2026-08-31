import os
import cv2
from flask import Flask, request, render_template, redirect
from werkzeug.utils import secure_filename
from evaluator import evaluate_screenshot
from modules.video_frame_extractor import extract_frames

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 # 50 MB limit for videos

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'mp4', 'webm', 'avi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        
        if not all_results:
            return render_template('result.html', results={"error": "Evaluation failed on all files."})
            
        # Aggregate scores (average)
        total_score = sum(r['design_craft_score'] for r in all_results)
        avg_score = round(total_score / len(all_results), 1)
        
        # We need the tier and max points from evaluator. We can just use the evaluator's helper.
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
            
        return render_template('result.html', results=aggregated_results)
            
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
