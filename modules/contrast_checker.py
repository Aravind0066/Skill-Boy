"""
Contrast & Readability Module
==============================
Evaluates the WCAG contrast ratio using Morphological Text-Region Isolation.

Instead of randomly sampling the entire image, this algorithm uses edge detection 
(Canny) and morphological operations (dilation) to precisely isolate text and UI 
elements. It extracts the foreground color directly from the content and samples 
the immediate background using a morphological "halo" mask, ensuring we are 
calculating the true readability contrast of the actual content.

Determinism guarantee:
  - Uses kmeans_deterministic() from kmeans_utils — pure NumPy, no RNG.
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

        # Resize uniformly for consistent performance
        small = cv2.resize(img, (400, int(400 * img.shape[0] / img.shape[1])))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # ── Morphological Text-Region Isolation ────────────────────────────────
        # Detect sharp edges (text and UI boundaries)
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate edges slightly to form the foreground content mask
        kernel_fg = np.ones((3, 3), np.uint8)
        mask_fg = cv2.dilate(edges, kernel_fg, iterations=1)
        
        # Dilate heavily to create a combined area, then subtract fg to get the halo (immediate background)
        kernel_bg = np.ones((7, 7), np.uint8)
        mask_combined = cv2.dilate(edges, kernel_bg, iterations=1)
        mask_halo = cv2.bitwise_xor(mask_combined, mask_fg)

        # Extract pixels using the masks
        fg_pixels = small[mask_fg > 0].astype(np.float32)
        bg_pixels = small[mask_halo > 0].astype(np.float32)

        # Fallback to whole image if morphological extraction failed (e.g., blank image)
        if len(fg_pixels) < 10 or len(bg_pixels) < 10:
            fg_pixels = small.reshape(-1, 3).astype(np.float32)
            bg_pixels = fg_pixels

        # ── Find Dominant Colors via Deterministic K-Means ────────────────────
        # Find dominant foreground color
        fg_labels, fg_centers = kmeans_deterministic(fg_pixels, 3)
        fg_counts = np.bincount(fg_labels.flatten())
        dominant_fg = fg_centers[np.argmax(fg_counts)]

        # Find dominant background color from the halo
        bg_labels, bg_centers = kmeans_deterministic(bg_pixels, 2)
        bg_counts = np.bincount(bg_labels.flatten())
        dominant_bg = bg_centers[np.argmax(bg_counts)]

        # Calculate contrast ratio between these specific regions
        max_ratio = get_contrast_ratio(dominant_fg, dominant_bg)

        # For thoroughness, also check top 2 fg vs top bg just in case the true text color was the 2nd most dominant in the edge mask
        if len(fg_counts) > 1:
            second_fg_idx = np.argsort(fg_counts)[-2]
            second_fg = fg_centers[second_fg_idx]
            ratio2 = get_contrast_ratio(second_fg, dominant_bg)
            max_ratio = max(max_ratio, ratio2)

        sub_score = normalize_contrast(max_ratio)

        if max_ratio >= 9.0:
            feedback = (f"WCAG AAA+ ({max_ratio:.2f}:1) — "
                        "Exceptional contrast inside text regions. Ideal for accessibility and professional clarity.")
        elif max_ratio >= 7.0:
            feedback = (f"WCAG AAA ({max_ratio:.2f}:1) — "
                        "Top-tier contrast detected by morphological analysis. Perfect for all text sizes.")
        elif max_ratio >= 4.5:
            feedback = (f"WCAG AA ({max_ratio:.2f}:1) — "
                        "Acceptable baseline contrast. Push toward 7:1 for elite-level readability.")
        elif max_ratio >= 3.0:
            feedback = (f"Below AA ({max_ratio:.2f}:1) — "
                        "Passes only for large text (18pt+). Text regions lack sufficient contrast against immediate background.")
        else:
            feedback = (f"WCAG FAIL ({max_ratio:.2f}:1) — "
                        "Unacceptable contrast in content areas. Text will be unreadable for many users.")

        return {
            "raw_value": round(max_ratio, 2),
            "sub_score": round(sub_score, 1),
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Contrast check error: {e}", "error": True}
