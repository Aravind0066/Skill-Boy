import cv2
import numpy as np

def luminance(color):
    """Relative luminance per WCAG 2.1 (color is [B, G, R] 0-255)."""
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
    Map raw WCAG contrast ratio to 0-100 sub-score.
    Curve: 1:1 → 0, 3:1 → 40, 4.5:1 → 70, 7:1 → 100+
    Formula: min(100, (ratio / 4.5) * 100) with a boost above 4.5.
    """
    if ratio >= 7.0:
        return 100
    elif ratio >= 4.5:
        # Linear 70→100 between 4.5 and 7
        return 70 + ((ratio - 4.5) / (7.0 - 4.5)) * 30
    elif ratio >= 3.0:
        # Linear 40→70 between 3 and 4.5
        return 40 + ((ratio - 3.0) / (4.5 - 3.0)) * 30
    else:
        # Linear 0→40 between 1 and 3
        return max(0, ((ratio - 1.0) / (3.0 - 1.0)) * 40)

def evaluate_contrast(image_path):
    """
    Returns:
        raw_value   — actual WCAG contrast ratio (float)
        sub_score   — normalized 0-100
        points      — points contribution (sub_score scaled later by evaluator)
        feedback    — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0, "feedback": "Could not load image.", "error": True}

        small = cv2.resize(img, (150, int(150 * img.shape[0] / img.shape[1])))
        pixels = small.reshape(-1, 3).astype(np.float32)

        K = 4
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

        # Find the pair with the highest contrast
        max_ratio = 1.0
        for i in range(len(centers)):
            for j in range(i + 1, len(centers)):
                r = get_contrast_ratio(centers[i], centers[j])
                if r > max_ratio:
                    max_ratio = r

        sub_score = normalize_contrast(max_ratio)

        if max_ratio >= 7.0:
            feedback = f"WCAG AAA ({max_ratio:.2f}:1) — Top-tier contrast. Perfect readability."
        elif max_ratio >= 4.5:
            feedback = f"WCAG AA ({max_ratio:.2f}:1) — Good contrast. Push toward 7:1 for elite marks."
        elif max_ratio >= 3.0:
            feedback = f"Below AA ({max_ratio:.2f}:1) — Only passes for large text. Darken text or lighten background."
        else:
            feedback = f"FAIL ({max_ratio:.2f}:1) — Contrast too low. Users cannot read this comfortably."

        return {"raw_value": round(max_ratio, 2), "sub_score": round(sub_score, 1), "feedback": feedback}

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0, "feedback": f"Contrast check error: {e}", "error": True}
