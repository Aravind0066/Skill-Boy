"""Small, screenshot-only penalties for obvious clipped visual elements."""

import cv2


def evaluate_polish(image_path):
    """Penalize contours that visibly run into the screenshot boundary."""
    try:
        image = cv2.imread(image_path)
        if image is None:
            return {"raw_value": "unavailable", "sub_score": 0, "penalty": 0, "feedback": "Could not load image.", "error": True}

        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 130)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        clipped = 0

        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            area = box_width * box_height
            if area < width * height * 0.65 and (
                x <= 1 or y <= 1 or x + box_width >= width - 1 or y + box_height >= height - 1
            ):
                clipped += 1

        penalty = min(20.0, clipped * 4.0)
        score = round(100.0 - penalty, 1)
        if clipped:
            feedback = f"{clipped} non-background visual element(s) touch the screenshot boundary; inspect for clipping."
        else:
            feedback = "No obvious clipped visual elements detected at the screenshot boundary."

        return {
            "raw_value": f"{clipped} boundary contacts",
            "sub_score": score,
            "penalty": penalty,
            "feedback": feedback,
        }
    except Exception as error:
        return {"raw_value": "error", "sub_score": 0, "penalty": 0, "feedback": f"Polish check error: {error}", "error": True}
