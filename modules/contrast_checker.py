"""
Contrast & Readability Module
==============================
Evaluates the WCAG contrast ratio between the dominant foreground and
background colors using K-Means clustering on pixel data.

Determinism guarantee:
  - Uses kmeans_deterministic() from kmeans_utils — pure NumPy, no RNG.
  - Identical image always produces identical scores.
"""

import cv2
import numpy as np
from modules.kmeans_utils import kmeans_deterministic


def luminance(color):
    """Relative luminance per WCAG 2.1 (color is [B, G, R] 0–255)."""
    b, g, r = [x / 255.0 for x in color]

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def get_contrast_ratio(c1, c2):
    l1, l2 = luminance(c1), luminance(c2)
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def normalize_contrast(ratio):
    """
    Strict professional scoring curve.
    AA compliance is baseline — NOT a high score.

      < 3:1  →  0–30   (WCAG FAIL)
      3–4.5  → 30–60   (large-text pass only)
      4.5–7  → 60–90   (AA — acceptable)
      7–9    → 90–100  (AAA)
      9+     → 100     (exceptional)
    """
    if ratio >= 9.0:
        return 100.0
    elif ratio >= 7.0:
        return 90.0 + ((ratio - 7.0) / (9.0 - 7.0)) * 10.0
    elif ratio >= 4.5:
        return 60.0 + ((ratio - 4.5) / (7.0 - 4.5)) * 30.0
    elif ratio >= 3.0:
        return 30.0 + ((ratio - 3.0) / (4.5 - 3.0)) * 30.0
    else:
        return max(0.0, ((ratio - 1.0) / (3.0 - 1.0)) * 30.0)


def evaluate_contrast(image_path):
    """
    Returns:
        raw_value  — actual WCAG contrast ratio (float)
        sub_score  — normalized 0–100
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        # Resize uniformly so pixel count is always identical for the same image
        small = cv2.resize(img, (200, int(200 * img.shape[0] / img.shape[1])))
        pixels = small.reshape(-1, 3).astype(np.float32)

        K = 5

        # ── DETERMINISTIC: pure-numpy kmeans, no RNG ──────────────────────────
        labels, centers = kmeans_deterministic(pixels, K)

        # Only compare clusters that cover ≥5 % of the image (foreground/bg pairs)
        label_counts = np.bincount(labels.flatten(), minlength=K)
        total = len(pixels)
        significant = [
            (i, centers[i])
            for i in range(K)
            if label_counts[i] / total >= 0.05
        ]

        max_ratio = 1.0
        pool = significant if len(significant) >= 2 else list(enumerate(centers))

        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                r = get_contrast_ratio(pool[i][1], pool[j][1])
                if r > max_ratio:
                    max_ratio = r

        sub_score = normalize_contrast(max_ratio)

        if max_ratio >= 9.0:
            feedback = (f"WCAG AAA+ ({max_ratio:.2f}:1) — "
                        "Exceptional contrast. Ideal for accessibility and professional clarity.")
        elif max_ratio >= 7.0:
            feedback = (f"WCAG AAA ({max_ratio:.2f}:1) — "
                        "Top-tier contrast. Perfect for all text sizes.")
        elif max_ratio >= 4.5:
            feedback = (f"WCAG AA ({max_ratio:.2f}:1) — "
                        "Acceptable baseline. Push toward 7:1 for elite-level readability.")
        elif max_ratio >= 3.0:
            feedback = (f"Below AA ({max_ratio:.2f}:1) — "
                        "Passes only for large text (18pt+). Darken text or lighten background.")
        else:
            feedback = (f"WCAG FAIL ({max_ratio:.2f}:1) — "
                        "Unacceptable contrast. Text will be unreadable for many users.")

        return {
            "raw_value": round(max_ratio, 2),
            "sub_score": round(sub_score, 1),
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Contrast check error: {e}", "error": True}
