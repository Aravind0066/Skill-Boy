"""Screenshot-observable typography hierarchy signals."""

import cv2
import numpy as np


def evaluate_typography(image_path):
    """Estimate text-size hierarchy from repeated compact horizontal components."""
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"raw_value": 0, "sub_score": 0, "feedback": "Could not load image.", "error": True}

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        threshold = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 9,
        )
        contours, _ = cv2.findContours(threshold, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        image_area = image.shape[0] * image.shape[1]
        heights = []

        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            area = width * height
            if 2 <= height <= max(12, image.shape[0] // 8) and 3 <= width <= image.shape[1] * 0.8:
                if 20 <= area <= image_area * 0.02:
                    heights.append(height)

        if len(heights) < 6:
            return {
                "raw_value": 1,
                "sub_score": 50.0,
                "feedback": "Too few text-like components for typography hierarchy analysis.",
            }

        heights = np.asarray(heights, dtype=float)
        percentiles = np.percentile(heights, [25, 50, 75])
        tiers = sum(
            abs(percentiles[index] - percentiles[index - 1]) >= 2
            for index in range(1, len(percentiles))
        ) + 1
        score = {1: 45.0, 2: 68.0, 3: 86.0}.get(min(tiers, 3), 86.0)
        spread = float(np.std(heights) / np.mean(heights)) if np.mean(heights) else 0.0
        score = min(100.0, score + 8.0) if spread >= 0.45 else score

        return {
            "raw_value": tiers,
            "sub_score": round(score, 1),
            "feedback": f"{tiers} detectable text-size tiers with measurable typographic scale separation.",
        }
    except Exception as error:
        return {"raw_value": 0, "sub_score": 0, "feedback": f"Typography check error: {error}", "error": True}
