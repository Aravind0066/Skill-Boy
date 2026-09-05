"""
Color Palette Discipline Module
================================
Evaluates how controlled the color palette is. A professional design uses
2–4 dominant colors with purpose; more than 5 signals poor palette discipline.

Also penalizes over-saturated palettes (garish/amateurish look) via HSV analysis.

Determinism guarantee:
  - Uses kmeans_deterministic() from kmeans_utils — pure NumPy, no RNG.
"""

import cv2
import numpy as np
from modules.kmeans_utils import kmeans_deterministic


def normalize_color_count(n):
    """
    Strict professional scoring based on dominant color count.
    Ideal: 2–3 colors (primary, secondary, accent).
    """
    if n < 2:
        return 35.0    # Monochrome — flat, no visual interest
    elif n <= 3:
        return 100.0   # Perfect: minimal, disciplined palette
    elif n == 4:
        return 88.0    # Still excellent
    elif n == 5:
        return 68.0    # Slightly complex but acceptable
    elif n == 6:
        return 48.0    # Getting chaotic
    elif n == 7:
        return 28.0    # Too many competing colors
    else:
        return max(0.0, 20.0 - (n - 8) * 5.0)


def evaluate_colors(image_path):
    """
    Returns:
        raw_value  — number of significant dominant colors detected
        sub_score  — normalized 0–100 (count + saturation penalty)
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        small = cv2.resize(img, (250, int(250 * img.shape[0] / img.shape[1])))
        pixels = small.reshape(-1, 3).astype(np.float32)

        K = 12

        # ── DETERMINISTIC: pure-numpy kmeans, no RNG ──────────────────────────
        labels, centers = kmeans_deterministic(pixels, K)

        label_counts = np.bincount(labels.flatten(), minlength=K)
        total = len(pixels)

        # Colors covering >5% of the image are "significant"
        significant_idx = [i for i in range(K) if label_counts[i] / total > 0.05]
        significant = len(significant_idx)

        # ── Saturation analysis ───────────────────────────────────────────────
        saturations = []
        for i in significant_idx:
            bgr = np.uint8([[centers[i]]])
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
            saturations.append(float(hsv[1]))  # S channel 0–255

        avg_sat = float(np.mean(saturations)) if saturations else 128.0

        # Penalty for garish over-saturation (avg S > 200 out of 255)
        saturation_penalty = 20.0 if avg_sat > 200 else 0.0

        count_score = normalize_color_count(significant)
        sub_score = max(0.0, count_score - saturation_penalty)

        # ── Feedback ──────────────────────────────────────────────────────────
        if significant <= 1:
            feedback = (f"{significant} dominant color — too monochromatic. "
                        "Add accent tones to create depth and hierarchy.")
        elif significant <= 3:
            feedback = (f"{significant} dominant colors — disciplined palette. "
                        "Strong design signal with clear visual identity.")
        elif significant <= 4:
            feedback = (f"{significant} dominant colors — solid palette. "
                        "Consider consolidating to 3 for tighter brand identity.")
        elif significant <= 6:
            feedback = (f"{significant} colors — slightly complex. "
                        "Trim to 3–4 colors; each should serve a clear purpose.")
        else:
            feedback = (f"{significant} significant colors — chaotic palette. "
                        "Establish a strict 3-color system: primary, secondary, accent.")

        if avg_sat > 200:
            feedback += " Palette is over-saturated — reduce vibrancy for a professional look."

        return {
            "raw_value": significant,
            "sub_score": round(sub_score, 1),
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Color check error: {e}", "error": True}
