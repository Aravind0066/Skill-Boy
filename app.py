import os
import tempfile
import cv2
import hashlib
from flask import Flask, g, request, render_template, redirect
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from evaluator import evaluate_screenshot
from modules.video_frame_extractor import extract_frames
from dotenv import load_dotenv
from supabase import create_client, Client
import json
import uuid
import traceback
from urllib.parse import urlparse
from modules.website_detector import detect_website

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_SERVER_KEY = SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY
SUPABASE_PERSIST_RESULTS = os.environ.get("SUPABASE_PERSIST_RESULTS", "true").lower() == "true"
WEBSITE_MIN_CONFIDENCE = int(os.environ.get("WEBSITE_MIN_CONFIDENCE", "55"))
supabase: Client = None

if SUPABASE_URL and SUPABASE_SERVER_KEY:
    parsed_supabase_url = urlparse(SUPABASE_URL)
    if parsed_supabase_url.scheme in {'http', 'https'} and parsed_supabase_url.netloc:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_SERVER_KEY)
            print("SUPABASE_STATUS=initialized")
        except Exception as error:
            print(f"SUPABASE_STATUS=error detail={error}")
else:
    print("SUPABASE_STATUS=disabled missing SUPABASE_URL or SUPABASE_SECRET_KEY")

app = Flask(__name__)

# Use /tmp for Render and local development so uploaded files are temporary.
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), 'skillblade_uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit for videos
MAX_IMAGE_COUNT = 12
MAX_IMAGE_DIMENSION = 1600

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


def unique_upload_path(filename):
    """Return a collision-free temporary path while preserving the extension."""
    safe_name = secure_filename(filename)
    stem, extension = os.path.splitext(safe_name)
    return os.path.join(
        app.config['UPLOAD_FOLDER'],
        f"{uuid.uuid4().hex}_{stem}{extension.lower()}"
    )


def normalize_uploaded_image(filepath):
    """Validate an image and cap its dimensions before CPU-heavy evaluation."""
    image = cv2.imread(filepath)
    if image is None:
        return False

    height, width = image.shape[:2]
    largest_dimension = max(height, width)
    if largest_dimension <= MAX_IMAGE_DIMENSION:
        return True

    scale = MAX_IMAGE_DIMENSION / largest_dimension
    resized = cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return bool(cv2.imwrite(filepath, resized))


def classify_error(error):
    """Return a safe, actionable category for logs and user-facing errors."""
    message = str(error).lower()
    if 'row-level security' in message or 'unauthorized' in message:
        return 'SUPABASE_STORAGE_RLS', 'Supabase Storage rejected the upload. Check the service-role key and the uploads bucket.'
    if 'schema cache' in message or 'column' in message and 'evaluations' in message:
        return 'SUPABASE_DATABASE_SCHEMA', 'Supabase rejected the evaluation record. Check that the evaluations table columns match the app.'
    if 'supabase' in message or 'postgrest' in message:
        return 'SUPABASE_CONNECTION', 'Supabase could not be reached or rejected the request. Check SUPABASE_URL, the key, and project status.'
    if 'decode' in message or 'image' in message:
        return 'IMAGE_PROCESSING', 'One uploaded file could not be decoded as a supported image.'
    return 'UNEXPECTED_PIPELINE_ERROR', 'The analysis pipeline failed. Check the Render log entry with the error ID.'

@app.route('/', methods=['GET', 'POST'])
def index():
    g.pipeline_stage = 'request_received'
    if request.method == 'POST':
        warnings = []
        mode = request.form.get('upload_mode', 'images')
        
        if 'files' not in request.files:
            return redirect(request.url)
        
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return redirect(request.url)

        if mode != 'video' and len(files) > MAX_IMAGE_COUNT:
            return render_template(
                'result.html',
                results={"error": f"Please upload no more than {MAX_IMAGE_COUNT} images per analysis."}
            )
            
        filepaths = []
        video_meta = None
        
        if mode == 'video':
            g.pipeline_stage = 'video_processing'
            # Handle single video
            file = files[0]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                video_path = unique_upload_path(filename)
                file.save(video_path)
                
                # Extract frames
                try:
                    frames, video_meta = extract_frames(video_path, target_fps=1.0, max_frames=20)
                    for i, frame in enumerate(frames):
                        frame_path = unique_upload_path(
                            f"frame_{i:03d}_{filename}.jpg"
                        )
                        cv2.imwrite(frame_path, frame)
                        filepaths.append(frame_path)
                    
                    # Clean up the original video to save space
                    os.remove(video_path)
                except Exception as e:
                    cleanup_files([video_path])
                    cleanup_files(filepaths)
                    return render_template('result.html', results={"error": f"Failed to process video: {str(e)}"})
        else:
            # Handle multiple images
            g.pipeline_stage = 'image_upload_processing'
            for file in files:
                if file and allowed_file(file.filename):
                    filepath = unique_upload_path(file.filename)
                    file.save(filepath)
                    if normalize_uploaded_image(filepath):
                        filepaths.append(filepath)
                    else:
                        cleanup_files([filepath])
        
        if not filepaths:
            return render_template('result.html', results={"error": "No valid files were processed."})

        eval_id = str(uuid.uuid4())
        player_id = request.cookies.get('skillblade_player_id') or uuid.uuid4().hex
        image_urls = []

        recognition = []
        for filepath in filepaths:
            detected = detect_website(filepath)
            recognition.append(detected)

        if any(item["confidence"] < WEBSITE_MIN_CONFIDENCE for item in recognition):
            cleanup_files(filepaths)
            return render_template(
                'result.html',
                results={
                    "error": "This upload does not look like a website screenshot. "
                    "Upload a browser or app UI capture with visible layout and content.",
                    "recognition": recognition,
                }
            ), 422

        if supabase and SUPABASE_PERSIST_RESULTS:
            g.pipeline_stage = 'supabase_storage_upload'
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
                    code, action = classify_error(e)
                    warning = f"{code}: {action}"
                    warnings.append(warning)
                    print(f"PIPELINE_WARNING code={code} stage={g.pipeline_stage} detail={e}")
        elif not supabase:
            warnings.append(
                'SUPABASE_NOT_CONFIGURED: Results are not being saved. Add SUPABASE_URL and SUPABASE_SECRET_KEY in Render.'
            )

        # Evaluate all screenshots/frames
        g.pipeline_stage = 'image_evaluation'
        all_results = []
        evaluation_errors = []
        evaluation_cache = {}
        for fp in filepaths:
            try:
                with open(fp, 'rb') as image_file:
                    image_hash = hashlib.sha256(image_file.read()).hexdigest()
                if image_hash not in evaluation_cache:
                    evaluation_cache[image_hash] = evaluate_screenshot(fp)
                res = evaluation_cache[image_hash]
            except Exception as error:
                res = {"error": str(error)}

            if "error" not in res:
                all_results.append(res)
            else:
                evaluation_errors.append(
                    f"{os.path.basename(fp)}: {res.get('error', 'Unknown evaluation error')}"
                )
        
        # Clean up temp files after evaluation
        cleanup_files(filepaths)

        if not all_results:
            details = " ".join(evaluation_errors)
            return render_template(
                'result.html',
                results={"error": f"Evaluation failed on all files. {details}"}
            )
            
        is_multi = len(all_results) > 1

        if is_multi:
            # Aggregate scores (average)
            avg_score = round(
                sum(r.get('design_craft_score', 0) for r in all_results) / len(all_results), 1
            )
            avg_design_craft = round(
                sum(r.get('design_craft_score', 0) for r in all_results) / len(all_results), 1
            )
            avg_modules = []
            for module in all_results[0].get('modules', []):
                module_key = module.get('key')
                module_scores = [
                    candidate.get('sub_score', 0)
                    for result in all_results
                    for candidate in result.get('modules', [])
                    if candidate.get('key') == module_key
                ]
                avg_sub_score = round(
                    sum(module_scores) / len(module_scores), 1
                ) if module_scores else 0
                avg_modules.append({
                    **module,
                    "sub_score": avg_sub_score,
                })

            avg_rubric = [
                {
                    "label": module.get("label", "Unknown"),
                    "score": module["sub_score"],
                    "points": round(
                        module["sub_score"] * module.get("weight_pct", 0) / 100, 1
                    ),
                    "weight": module.get("weight_pct", 0),
                    "automated": True,
                }
                for module in avg_modules
            ]
            
            from evaluator import get_tier, tier_description, MAX_POINTS
            tier_name, tier_icon, tier_key = get_tier(avg_score)
            avg_points = round((avg_score / 100) * MAX_POINTS, 1)
            
            aggregated_results = {
                "is_multi": True,
                "mode": mode,
                "file_count": len(all_results),
                "video_meta": video_meta,
                "design_craft_score": avg_design_craft,
                "total_score": avg_score,
                "design_craft_points": round((avg_design_craft / 100) * MAX_POINTS, 1),
                "rubric": avg_rubric,
                "max_points": MAX_POINTS,
                "tier_name": tier_name,
                "tier_icon": tier_icon,
                "tier_key": tier_key,
                "tier_desc": tier_description(tier_name),
                "frames": all_results,
                "modules": avg_modules,
            }
        else:
            aggregated_results = all_results[0]
            aggregated_results["is_multi"] = False
            aggregated_results["mode"] = mode
            aggregated_results["file_count"] = 1
            
        # Store in Supabase if configured
        if supabase and SUPABASE_PERSIST_RESULTS:
            try:
                g.pipeline_stage = 'supabase_database_insert'
                # Round-trip through JSON to convert any numpy types to native Python
                # NOTE: Keep results_json clean — don't inject id/image_urls into it
                safe_results = json.loads(json.dumps(aggregated_results, default=str))
                
                db_record = {
                    "id": eval_id,
                    "player_id": player_id,
                    "mode": mode,
                    "file_count": int(safe_results.get("file_count", 1)),
                    "design_craft_score": float(safe_results.get("design_craft_score", 0)),
                    "tier_name": str(safe_results.get("tier_name", "Unknown")),
                    "tier_key": str(safe_results.get("tier_key", "unknown")),
                    "tier_icon": str(safe_results.get("tier_icon", "")),
                    "website_confidence": min(item["confidence"] for item in recognition),
                    "results_json": safe_results
                }
                supabase.table("evaluations").insert(db_record).execute()
            except Exception as e:
                code, action = classify_error(e)
                warnings.append(f"{code}: {action}")
                print(f"PIPELINE_WARNING code={code} stage={g.pipeline_stage} detail={e}")

        # Attach eval metadata for the result page (after DB write, so results_json stays clean)
        aggregated_results["id"] = eval_id
        aggregated_results["image_urls"] = image_urls
        aggregated_results["pipeline_warnings"] = warnings

        response = render_template('result.html', results=aggregated_results)
        response = app.make_response(response)
        response.set_cookie('skillblade_player_id', player_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite='Lax')
        return response
            
    return render_template('index.html')


@app.route('/history')
def history_page():
    """Render the current player's persisted score history."""
    return render_template('history.html')


@app.route('/api/history')
def history():
    """Return the current player's persisted score history."""
    if not supabase or not SUPABASE_PERSIST_RESULTS:
        return {"error": "Score history is not configured."}, 503

    player_id = request.cookies.get('skillblade_player_id')
    if not player_id:
        return {"evaluations": []}

    try:
        response = supabase.table("evaluations").select(
            "id, created_at, mode, file_count, design_craft_score, tier_name, tier_key, website_confidence"
        ).eq("player_id", player_id).order("created_at", desc=True).limit(50).execute()
        return {"evaluations": response.data or []}
    except Exception as error:
        code, action = classify_error(error)
        print(f"PIPELINE_WARNING code={code} stage=history_read detail={error}")
        return {"error": action}, 500


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.errorhandler(413)
def request_too_large(error):
    return render_template(
        'result.html',
        results={"error": "The upload is too large. Please use smaller images or fewer files."}
    ), 413


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    error_id = uuid.uuid4().hex[:8]
    code, action = classify_error(error)
    stage = getattr(g, 'pipeline_stage', 'unknown')
    print(
        f"PIPELINE_ERROR id={error_id} code={code} stage={stage} "
        f"type={type(error).__name__} detail={error}"
    )
    traceback.print_exc()
    return render_template(
        'result.html',
        results={
            "error": f"{code} (error ID: {error_id})\n{action}"
        }
    ), 500


# Gunicorn uses this Flask object as the WSGI application.
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
