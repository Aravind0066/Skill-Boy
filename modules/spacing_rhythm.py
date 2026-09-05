"""
Spacing Rhythm Module
======================
Detects vertical gaps between UI element bounding boxes and evaluates two
aspects of spacing quality:

  1. 8px-grid adherence (60% weight) — are gaps multiples of 8px ± 3px?
  2. Gap consistency (40% weight)    — are gaps uniform (low coefficient of variation)?

Both dimensions matter: a design can use 8px multiples but apply them
inconsistently, or be consistent but not follow a standard grid.
"""

import cv2
import numpy as np


def evaluate_spacing(image_path):
    """
    Returns:
        raw_value  — % of gaps that are 8px-grid rhythmic
        sub_score  — combined rhythm + consistency score, 0–100
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 130)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w > 25 and h > 12:
                boxes.append((y, y + h))

        if len(boxes) < 4:
            return {
                "raw_value": 50,
                "sub_score": 50,
                "feedback": "Too few elements for spacing rhythm analysis.",
            }

        boxes.sort(key=lambda b: b[0])

        gaps = []
        for i in range(1, len(boxes)):
            gap = boxes[i][0] - boxes[i - 1][1]
            if 2 <= gap <= 200:  # Exclude overlap and huge section breaks
                gaps.append(gap)

        if not gaps:
            return {
                "raw_value": 0,
                "sub_score": 40,
                "feedback": "Could not compute spacing rhythm from detected elements.",
            }

        # ── 1. 8px-grid adherence ─────────────────────────────────────────────
        base = 8
        rhythmic = sum(
            1 for g in gaps if min(g % base, base - (g % base)) <= 3
        )
        rhythm_pct = (rhythmic / len(gaps)) * 100.0

        # ── 2. Gap consistency (coefficient of variation) ────────────────────
        gap_arr = np.array(gaps, dtype=float)
        mean_gap = float(np.mean(gap_arr))
        cv_pct = (float(np.std(gap_arr)) / mean_gap * 100.0) if mean_gap > 0 else 100.0

        # Low CoV = more consistent = higher score
        consistency_score = max(0.0, 100.0 - cv_pct * 0.8)

        # ── Combined score ────────────────────────────────────────────────────
        sub_score = round(min(100.0, (rhythm_pct * 0.6) + (consistency_score * 0.4)), 1)

        if sub_score >= 80:
            feedback = (f"{rhythm_pct:.0f}% rhythmic gaps — "
                        "excellent 8px spacing system with consistent vertical rhythm.")
        elif sub_score >= 60:
            feedback = (f"{rhythm_pct:.0f}% rhythmic gaps — "
                        "good spacing base. Align remaining gaps to the nearest 8px multiple.")
        elif sub_score >= 35:
            feedback = (f"{rhythm_pct:.0f}% rhythmic gaps — "
                        "inconsistent spacing. Adopt a spacing scale: 8, 16, 24, 32, 48px.")
        else:
            feedback = (f"{rhythm_pct:.0f}% rhythmic gaps — "
                        "no spacing system detected. Gaps appear arbitrary.")

        return {
            "raw_value": round(rhythm_pct, 1),
            "sub_score": sub_score,
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Spacing check error: {e}", "error": True}
