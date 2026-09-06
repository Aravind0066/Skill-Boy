"""
Visual Balance & Macro Whitespace Module (NEW)
==============================================
Calculates the Content-to-Whitespace ratio.

Professional UI design relies heavily on "Macro Whitespace" to prevent cognitive 
overload. This module generates a composite mask of all UI elements (text, images, 
containers) and calculates the percentage of active content versus negative space.

Ideal density is typically between 25% and 40% active content. 
Too low = sparse/empty. Too high = cluttered/overwhelming.
"""

import cv2
import numpy as np


def normalize_density(density_pct):
    """
    Score the active content density percentage.
    Ideal: 25% - 40%
    Sparse: < 20%
    Cluttered: > 50%
    """
    if 25.0 <= density_pct <= 40.0:
        return 100.0
    elif 20.0 <= density_pct < 25.0:
        # Sparse but ok: 20->80, 25->100
        return 80.0 + ((density_pct - 20.0) / 5.0) * 20.0
    elif 40.0 < density_pct <= 50.0:
        # Getting cluttered: 40->100, 50->60
        return 100.0 - ((density_pct - 40.0) / 10.0) * 40.0
    elif density_pct > 50.0:
        # Highly cluttered: drops fast
        return max(0.0, 60.0 - ((density_pct - 50.0) * 2.0))
    else:
        # Very sparse: < 20%
        return max(0.0, 80.0 - ((20.0 - density_pct) * 4.0))


def evaluate_balance(image_path):
    """
    Returns:
        raw_value  — formatted string like '32% Content'
        sub_score  — normalized 0–100
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": "0% Content", "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        img_h, img_w = img.shape[:2]
        total_area = float(img_h * img_w)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        # Create a blank mask to draw all UI elements
        mask = np.zeros((img_h, img_w), dtype=np.uint8)

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Filter tiny noise pixels AND near-fullscreen backgrounds
            if w > 10 and h > 10 and (w * h) < (img_h * img_w * 0.5):
                # Fill the bounding box area in the mask
                cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

        # Count active pixels in the composite mask
        content_area = cv2.countNonZero(mask)
        density_pct = (content_area / total_area) * 100.0
        
        sub_score = normalize_density(density_pct)
        raw_display = f"{density_pct:.1f}% Content"
        
        whitespace_pct = 100.0 - density_pct

        if sub_score >= 90:
            feedback = (f"Macro Whitespace ({whitespace_pct:.1f}%) — perfect visual balance. "
                        "The design breathes well without feeling empty.")
        elif density_pct > 40.0:
            feedback = (f"Macro Whitespace ({whitespace_pct:.1f}%) — slightly cluttered. "
                        "Increase padding and negative space between sections.")
        elif density_pct < 25.0:
            feedback = (f"Macro Whitespace ({whitespace_pct:.1f}%) — slightly sparse. "
                        "The layout feels empty; consider scaling up elements or adding content density.")
        
        # Override for extremes
        if density_pct > 55.0:
            feedback = (f"Macro Whitespace ({whitespace_pct:.1f}%) — highly cluttered layout! "
                        "Cognitive overload is likely. Drastically increase negative space.")
        elif density_pct < 15.0:
            feedback = (f"Macro Whitespace ({whitespace_pct:.1f}%) — far too sparse. "
                        "There is barely any content anchoring the design.")

        return {
            "raw_value": raw_display,
            "sub_score": round(sub_score, 1),
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": "Error", "sub_score": 0,
                "feedback": f"Balance check error: {e}", "error": True}
