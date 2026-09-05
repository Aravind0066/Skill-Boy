"""
Grid & Layout Alignment Module
================================
Detects vertical alignment columns by clustering the x-origin of significant
UI element bounding boxes. Fewer distinct columns = tighter grid discipline.

Scoring curve is stricter than before — more than 30 distinct columns on a
standard viewport is near-zero score regardless of other factors.
"""

import cv2
import numpy as np


def normalize_alignment(num_lines, img_width):
    """
    Professional scoring: fewer distinct alignment columns = better grid.
    Scale thresholds proportionally to image width.

    Ideal  : ≤ 10 columns for a standard 1400px viewport → 100
    OK     : 10–30 columns → linear decay 100 → 45
    Weak   : > 30 columns  → further decay toward 0
    """
    scale = img_width / 1400.0
    ideal_max = 10 * scale
    poor_threshold = 30 * scale

    if num_lines <= ideal_max:
        return 100.0
    elif num_lines <= poor_threshold:
        ratio = (num_lines - ideal_max) / (poor_threshold - ideal_max)
        return round(100.0 - ratio * 55.0, 1)
    else:
        return max(0.0, round(45.0 - (num_lines - poor_threshold) * 0.9, 1))


def evaluate_grid(image_path):
    """
    Returns:
        raw_value  — number of distinct vertical alignment columns detected
        sub_score  — normalized 0–100
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
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Filter noise and near-fullscreen elements
            if w > 15 and h > 8 and (w * h) < (img_h * img_w * 0.5):
                x_starts.append(x)

        if not x_starts:
            return {
                "raw_value": 0,
                "sub_score": 50,
                "feedback": "Could not detect clear UI elements. Manual review recommended.",
            }

        x_starts.sort()

        # Cluster with 16px tolerance (2 × 8px grid unit)
        # Use averaged cluster centroid for accurate column position
        columns = []
        current_sum = float(x_starts[0])
        current_count = 1
        current_centroid = float(x_starts[0])

        for x in x_starts[1:]:
            if x - current_centroid > 16:
                columns.append(current_sum / current_count)
                current_sum = float(x)
                current_count = 1
                current_centroid = float(x)
            else:
                current_sum += x
                current_count += 1
                current_centroid = current_sum / current_count

        columns.append(current_sum / current_count)

        num_lines = len(columns)
        sub_score = normalize_alignment(num_lines, img_w)

        if sub_score >= 90:
            feedback = (f"{num_lines} alignment columns — tight grid. "
                        "Elements align cleanly to a consistent column structure.")
        elif sub_score >= 70:
            feedback = (f"{num_lines} alignment columns — solid grid, "
                        "but some elements break the columns. Enforce strict alignment.")
        elif sub_score >= 45:
            feedback = (f"{num_lines} alignment columns — weak grid discipline. "
                        "Adopt a 12-column grid and snap all elements to it.")
        else:
            feedback = (f"{num_lines} alignment columns — no discernible grid. "
                        "Layout appears ad-hoc; use a column framework.")

        return {
            "raw_value": num_lines,
            "sub_score": round(sub_score, 1),
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Grid check error: {e}", "error": True}
