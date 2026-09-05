"""
Component Consistency Module
==============================
Detects button-like rectangular contours and measures how uniform their
heights are using the coefficient of variation (CoV %). Lower variance
means more systematic component design.

Aspect ratio range expanded slightly to catch more pill-shaped and
icon-button variants common in modern UI.
"""

import cv2
import numpy as np


def evaluate_buttons(image_path):
    """
    Returns:
        raw_value  — CoV % of button heights (lower = more consistent)
        sub_score  — normalized 0–100 (inverted: low variance = high score)
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        button_heights = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            aspect = w / h if h > 0 else 0
            # Buttons: height 18–90px, aspect ratio 1.5–12 (covers pill, rect, wide-cta)
            if 18 <= h <= 90 and 1.5 <= aspect <= 12:
                button_heights.append(h)

        if len(button_heights) < 2:
            return {
                "raw_value": 0,
                "sub_score": 55,
                "feedback": (
                    "Too few button-like elements detected. "
                    "Design may lack clear CTAs or interactive components."
                ),
            }

        heights = np.array(button_heights, dtype=float)
        cv_pct = (np.std(heights) / np.mean(heights)) * 100.0

        # CoV → sub_score (inverted)
        #   0–5%   → 100     (perfectly uniform)
        #   5–15%  → 80–100  (very consistent)
        #  15–30%  → 30–80   (moderate variance)
        #  >30%    → 0–30    (inconsistent)
        if cv_pct <= 5:
            sub_score = 100.0
        elif cv_pct <= 15:
            sub_score = 80.0 + (15.0 - cv_pct) / 10.0 * 20.0
        elif cv_pct <= 30:
            sub_score = 30.0 + (30.0 - cv_pct) / 15.0 * 50.0
        else:
            sub_score = max(0.0, 30.0 - (cv_pct - 30.0) * 0.5)

        n = len(button_heights)
        if sub_score >= 90:
            feedback = (f"{n} interactive elements, {cv_pct:.1f}% height variance — "
                        "very consistent components. Clean component system.")
        elif sub_score >= 65:
            feedback = (f"{n} interactive elements, {cv_pct:.1f}% height variance — "
                        "mostly consistent. Standardize padding and height tokens.")
        elif sub_score >= 35:
            feedback = (f"{n} interactive elements, {cv_pct:.1f}% height variance — "
                        "inconsistent components. Define a single button height and stick to it.")
        else:
            feedback = (f"{n} interactive elements, {cv_pct:.1f}% height variance — "
                        "highly inconsistent. Components appear custom-sized per instance.")

        return {
            "raw_value": round(cv_pct, 1),
            "sub_score": round(sub_score, 1),
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Button check error: {e}", "error": True}
