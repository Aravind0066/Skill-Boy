"""
Grid & Layout Alignment Module
================================
Evaluates the 2D Spatial Grid (Columns and Rows) of the design.

Professional UI design requires both vertical column alignment and horizontal 
baseline (row) alignment. This module clusters both X and Y coordinates of 
detected elements to measure the total structural discipline of the layout.
"""

import cv2
import numpy as np


def normalize_2d_grid(num_cols, num_rows, img_w, img_h):
    """
    Professional scoring: strict evaluation of both 2D axes.
    Scale thresholds proportionally to image dimensions.
    """
    scale_x = img_w / 1400.0
    scale_y = img_h / 900.0
    
    ideal_cols = 12 * scale_x
    ideal_rows = 15 * scale_y
    
    poor_cols = 35 * scale_x
    poor_rows = 40 * scale_y

    # Calculate column score
    if num_cols <= ideal_cols:
        score_x = 100.0
    elif num_cols <= poor_cols:
        ratio = (num_cols - ideal_cols) / (poor_cols - ideal_cols)
        score_x = 100.0 - ratio * 55.0
    else:
        score_x = max(0.0, 45.0 - (num_cols - poor_cols) * 0.9)

    # Calculate row score
    if num_rows <= ideal_rows:
        score_y = 100.0
    elif num_rows <= poor_rows:
        ratio = (num_rows - ideal_rows) / (poor_rows - ideal_rows)
        score_y = 100.0 - ratio * 55.0
    else:
        score_y = max(0.0, 45.0 - (num_rows - poor_rows) * 0.9)

    # Final score is a weighted average favoring columns slightly more
    # (since vertical scrolling naturally creates more rows)
    return round((score_x * 0.6) + (score_y * 0.4), 1)


def cluster_coordinates(coords, tolerance):
    """Clusters a sorted list of coordinates using a sliding window average."""
    if not coords:
        return []
    
    clusters = []
    current_sum = float(coords[0])
    current_count = 1
    current_centroid = float(coords[0])

    for val in coords[1:]:
        if val - current_centroid > tolerance:
            clusters.append(current_sum / current_count)
            current_sum = float(val)
            current_count = 1
            current_centroid = float(val)
        else:
            current_sum += val
            current_count += 1
            current_centroid = current_sum / current_count

    clusters.append(current_sum / current_count)
    return clusters


def evaluate_grid(image_path):
    """
    Returns:
        raw_value  — formatted string like '12 Cols, 15 Rows'
        sub_score  — normalized 0–100 combining both axes
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        img_h, img_w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 130)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        x_starts = []
        y_starts = []
        
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Filter noise and near-fullscreen backgrounds
            if w > 15 and h > 8 and (w * h) < (img_h * img_w * 0.5):
                x_starts.append(x)
                y_starts.append(y)

        if not x_starts:
            return {
                "raw_value": "0 Cols, 0 Rows",
                "sub_score": 50,
                "feedback": "Could not detect clear UI elements. Manual review recommended.",
            }

        x_starts.sort()
        y_starts.sort()

        # Cluster X with 16px tolerance (2 × 8px grid unit)
        columns = cluster_coordinates(x_starts, tolerance=16)
        
        # Cluster Y with 12px tolerance (stricter baseline alignment)
        rows = cluster_coordinates(y_starts, tolerance=12)

        num_cols = len(columns)
        num_rows = len(rows)
        
        sub_score = normalize_2d_grid(num_cols, num_rows, img_w, img_h)
        raw_display = f"{num_cols} Cols, {num_rows} Rows"

        if sub_score >= 90:
            feedback = (f"2D Spatial Grid ({raw_display}) — incredibly tight structural discipline. "
                        "Elements align perfectly on both axes.")
        elif sub_score >= 70:
            feedback = (f"2D Spatial Grid ({raw_display}) — solid structure, "
                        "but some elements break alignment. Enforce strict baselines.")
        elif sub_score >= 45:
            feedback = (f"2D Spatial Grid ({raw_display}) — weak 2D grid discipline. "
                        "Adopt a strict column framework and horizontal baseline rhythm.")
        else:
            feedback = (f"2D Spatial Grid ({raw_display}) — no discernible grid detected. "
                        "Layout appears ad-hoc; elements are scattered across both axes.")

        return {
            "raw_value": raw_display,
            "sub_score": sub_score,
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": "Error", "sub_score": 0,
                "feedback": f"Grid check error: {e}", "error": True}
