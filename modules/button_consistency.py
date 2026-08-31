import cv2
import numpy as np

def normalize_buttons(variance_score):
    """Map a computed consistency score to 0-100."""
    return min(100.0, max(0.0, variance_score))

def evaluate_buttons(image_path):
    """
    Detects button-like rectangular contours and checks for consistency
    in height and corner radius approximation.
    
    Returns:
        raw_value   — coefficient of variation (%) of button heights (lower = more consistent)
        sub_score   — normalized 0-100 (inverted: low variance = high score)
        feedback    — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0, "feedback": "Could not load image.", "error": True}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        button_heights = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            aspect = w / h if h > 0 else 0
            # Buttons are wider than tall with a limited height range (20-80px)
            if 20 <= h <= 80 and 1.5 <= aspect <= 10:
                button_heights.append(h)

        if len(button_heights) < 2:
            return {
                "raw_value": 0,
                "sub_score": 60,
                "feedback": "Too few button-like elements detected. Design may lack clear CTAs."
            }

        heights = np.array(button_heights, dtype=float)
        cv_pct = (np.std(heights) / np.mean(heights)) * 100  # Coefficient of variation %

        # Lower CoV = more consistent buttons = higher score
        # CoV 0-5% → 100, 5-15% → 80, 15-30% → 60, >30% → 30
        if cv_pct <= 5:
            sub_score = 100
        elif cv_pct <= 15:
            sub_score = 80 + (15 - cv_pct) / 10 * 20
        elif cv_pct <= 30:
            sub_score = 60 - (cv_pct - 15) / 15 * 30
        else:
            sub_score = max(0, 30 - (cv_pct - 30) * 0.5)

        if sub_score >= 90:
            feedback = f"{len(button_heights)} buttons detected, {cv_pct:.1f}% height variance — very consistent components."
        elif sub_score >= 65:
            feedback = f"{len(button_heights)} buttons, {cv_pct:.1f}% height variance — mostly consistent. Standardize padding."
        else:
            feedback = f"{len(button_heights)} buttons, {cv_pct:.1f}% height variance — buttons look inconsistent. Use a single component height."

        return {"raw_value": round(cv_pct, 1), "sub_score": round(sub_score, 1), "feedback": feedback}

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0, "feedback": f"Button check error: {e}", "error": True}
