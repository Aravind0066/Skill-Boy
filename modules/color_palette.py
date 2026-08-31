import cv2
import numpy as np

def normalize_color_count(n):
    """
    Map dominant-color count to 0-100 sub-score.
    Ideal: 2-4 colors → 100. Monochrome or >6 → penalized.
    """
    if n < 2:
        return 45   # Monochrome — flat, no depth
    elif n <= 4:
        return 100  # Perfect palette discipline
    elif n == 5:
        return 80
    elif n == 6:
        return 60
    elif n == 7:
        return 40
    else:
        return max(0, 40 - (n - 7) * 8)  # Decreasing penalty

def evaluate_colors(image_path):
    """
    Returns:
        raw_value   — number of significant dominant colors detected
        sub_score   — normalized 0-100
        feedback    — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0, "feedback": "Could not load image.", "error": True}

        small = cv2.resize(img, (200, int(200 * img.shape[0] / img.shape[1])))
        pixels = small.reshape(-1, 3).astype(np.float32)

        K = 10
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

        unique, counts = np.unique(labels, return_counts=True)
        total = len(pixels)

        # A color is "significant" if it covers > 5% of the image
        significant = sum(1 for c in counts if c / total > 0.05)

        sub_score = normalize_color_count(significant)

        if significant <= 1:
            feedback = f"{significant} dominant color — too monochromatic. Add accent or background variation."
        elif significant <= 4:
            feedback = f"{significant} dominant colors — disciplined, cohesive palette. Great design signal."
        elif significant <= 6:
            feedback = f"{significant} colors — slightly crowded palette. Trim to 3-4 for tighter identity."
        else:
            feedback = f"{significant} significant colors — chaotic palette. Pick a 3-color system and stick to it."

        return {"raw_value": significant, "sub_score": round(sub_score, 1), "feedback": feedback}

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0, "feedback": f"Color check error: {e}", "error": True}
