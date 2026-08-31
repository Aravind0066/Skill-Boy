import cv2
import numpy as np

def normalize_spacing(score_raw):
    """Pass through — spacing score is already 0-100 based on rhythm ratio."""
    return min(100.0, max(0.0, score_raw))

def evaluate_spacing(image_path):
    """
    Detects vertical gaps between contour bounding boxes and checks
    whether they follow a consistent spacing rhythm (multiples of 8px).
    
    Returns:
        raw_value   — % of gaps that are "rhythmic" (multiple of 8 ± 3px tolerance)
        sub_score   — normalized 0-100
        feedback    — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0, "feedback": "Could not load image.", "error": True}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Get bounding boxes, filter noise
        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 30 and h > 15:
                boxes.append((y, y + h))  # (top, bottom)

        if len(boxes) < 4:
            return {"raw_value": 50, "sub_score": 50, "feedback": "Too few elements detected for spacing rhythm analysis."}

        # Sort by y-position
        boxes.sort(key=lambda b: b[0])

        # Compute vertical gaps between successive boxes
        gaps = []
        for i in range(1, len(boxes)):
            gap = boxes[i][0] - boxes[i - 1][1]
            if 2 <= gap <= 200:  # Ignore negative overlap and very large gaps
                gaps.append(gap)

        if not gaps:
            return {"raw_value": 0, "sub_score": 40, "feedback": "Could not compute spacing rhythm."}

        # Check how many gaps are "multiples of 8" within ±3px tolerance
        base = 8
        rhythmic = sum(1 for g in gaps if min(g % base, base - (g % base)) <= 3)
        rhythm_pct = (rhythmic / len(gaps)) * 100

        sub_score = normalize_spacing(rhythm_pct)

        if rhythm_pct >= 75:
            feedback = f"{rhythm_pct:.0f}% rhythmic gaps — excellent 8px spacing grid. Consistent vertical rhythm."
        elif rhythm_pct >= 50:
            feedback = f"{rhythm_pct:.0f}% rhythmic gaps — good start. Align remaining gaps to nearest 8px multiple."
        elif rhythm_pct >= 30:
            feedback = f"{rhythm_pct:.0f}% rhythmic gaps — inconsistent. Adopt a spacing scale (8, 16, 24, 32px)."
        else:
            feedback = f"{rhythm_pct:.0f}% rhythmic gaps — no spacing system detected. Gaps appear arbitrary."

        return {"raw_value": round(rhythm_pct, 1), "sub_score": round(sub_score, 1), "feedback": feedback}

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0, "feedback": f"Spacing check error: {e}", "error": True}
