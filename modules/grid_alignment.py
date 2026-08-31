import cv2
import numpy as np

def normalize_alignment(num_lines, img_width):
    """
    Map number of distinct vertical alignment lines (relative to image width) to 0-100.
    Fewer lines = tighter grid discipline = higher score.
    We compare against image width because wider images naturally have more lines.
    """
    # Ideal: ~3-8 distinct alignment lines for a 1400px-wide screenshot
    # Scale threshold by image width
    scale = img_width / 1400.0
    ideal_max = 12 * scale
    poor_threshold = 35 * scale

    if num_lines <= ideal_max:
        return 100
    elif num_lines <= poor_threshold:
        # Linear decay: 100 → 40
        ratio = (num_lines - ideal_max) / (poor_threshold - ideal_max)
        return round(100 - ratio * 60, 1)
    else:
        # Below poor threshold
        return max(0, round(40 - (num_lines - poor_threshold) * 0.5, 1))

def evaluate_grid(image_path):
    """
    Returns:
        raw_value   — number of distinct vertical alignment lines detected
        sub_score   — normalized 0-100
        feedback    — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0, "feedback": "Could not load image.", "error": True}

        img_width = img.shape[1]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        x_starts = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 20 and h > 10:
                x_starts.append(x)

        if not x_starts:
            return {"raw_value": 0, "sub_score": 50, "feedback": "Could not detect clear UI elements. Manual review recommended."}

        x_starts.sort()
        # Cluster with a 12px tolerance window
        columns = []
        current = x_starts[0]
        for x in x_starts[1:]:
            if x - current > 12:
                columns.append(current)
                current = x
            else:
                current = (current + x) / 2
        columns.append(current)

        num_lines = len(columns)
        sub_score = normalize_alignment(num_lines, img_width)

        if sub_score >= 90:
            feedback = f"{num_lines} alignment lines — tight grid system. Elements align cleanly to a consistent structure."
        elif sub_score >= 65:
            feedback = f"{num_lines} alignment lines — decent grid, but some elements break the columns. Snap to an 8 or 12-column grid."
        elif sub_score >= 40:
            feedback = f"{num_lines} alignment lines — weak grid discipline. Large portions of the UI appear scattered."
        else:
            feedback = f"{num_lines} alignment lines — no discernible grid. Layout appears built without a column system."

        return {"raw_value": num_lines, "sub_score": round(sub_score, 1), "feedback": feedback}

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0, "feedback": f"Grid check error: {e}", "error": True}
