import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Add uuid import
content = content.replace('import json', 'import json\nimport uuid')

# 2. Modify index route to include upload logic
new_index_logic = """        if not filepaths:
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

        # Evaluate all screenshots/frames"""

content = content.replace("""        if not filepaths:
            return render_template('result.html', results={"error": "No valid files were processed."})

        # Evaluate all screenshots/frames""", new_index_logic)

# 3. Add to aggregated_results and db_record
new_db_insert = """        # Store in Supabase if configured
        if supabase:
            aggregated_results["id"] = eval_id
            aggregated_results["image_urls"] = image_urls
            try:
                # Round-trip through JSON to convert any numpy types to native Python
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
                print(f"Failed to store result in Supabase: {e}")"""

content = re.sub(r'        # Store in Supabase if configured.*?print\(f"Failed to store result in Supabase: \{e\}"\)', new_db_insert, content, flags=re.DOTALL)

# 4. Add history routes
history_routes = """
@app.route('/history')
def history():
    if not supabase:
        return render_template('history.html', error="Supabase is not configured.", evaluations=[])
    
    try:
        response = supabase.table('evaluations').select('id, created_at, mode, file_count, design_craft_score, tier_name, tier_key, tier_icon, image_urls').order('created_at', desc=True).execute()
        return render_template('history.html', evaluations=response.data)
    except Exception as e:
        return render_template('history.html', error=f"Failed to fetch history: {str(e)}", evaluations=[])

@app.route('/history/<uuid:eval_id>')
def history_detail(eval_id):
    if not supabase:
        return redirect('/')
    
    try:
        response = supabase.table('evaluations').select('results_json').eq('id', str(eval_id)).execute()
        if not response.data:
            return redirect('/history')
            
        results = response.data[0]['results_json']
        return render_template('result.html', results=results)
    except Exception as e:
        return redirect('/history')
"""

content = content.replace("    return render_template('index.html')", "    return render_template('index.html')\n" + history_routes)

with open('app.py', 'w') as f:
    f.write(content)
