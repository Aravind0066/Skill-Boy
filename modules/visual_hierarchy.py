"""
Visual Hierarchy Module (NEW)
==============================
Detects whether the design has a clear visual hierarchy — the #1 indicator
of design craft. Analyzes the size distribution of significant UI elements
and checks for distinct size tiers (hero / section / card / detail).

A flat design where all elements are the same size scores very low.
A design with a clear focal point and 3–4 distinct size tiers scores highest.
"""

import cv2
import numpy as np


def evaluate_hierarchy(image_path):
    """
    Returns:
        raw_value  — number of distinct size tiers detected (1–4)
        sub_score  — normalized 0–100
        feedback   — human-readable verdict
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"raw_value": 0, "sub_score": 0,
                    "feedback": "Could not load image.", "error": True}

        img_area = img.shape[0] * img.shape[1]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        # Collect areas of meaningful elements (filter noise + full-image bg)
        areas = []
        for c in contours:
            area = float(cv2.contourArea(c))
            if img_area * 0.0005 < area < img_area * 0.90:
                areas.append(area)

        if len(areas) < 5:
            return {
                "raw_value": 1,
                "sub_score": 40.0,
                "feedback": "Too few distinct elements for hierarchy analysis. "
                            "Ensure the design has multiple visible UI components.",
            }

        areas.sort(reverse=True)
        max_area = areas[0]

        # Normalize areas relative to the largest element
        norm = [a / max_area for a in areas]

        # Bucket into 4 standard size tiers
        tier_hero    = sum(1 for a in norm if a > 0.60)           # dominant focal element
        tier_section = sum(1 for a in norm if 0.20 < a <= 0.60)   # section containers
        tier_card    = sum(1 for a in norm if 0.05 < a <= 0.20)   # cards, widgets
        tier_detail  = sum(1 for a in norm if a <= 0.05)          # labels, icons, details

        active_tiers = sum([
            tier_hero > 0,
            tier_section > 0,
            tier_card > 0,
            tier_detail > 0,
        ])

        # Base score from number of active tiers
        base_scores = {4: 90, 3: 72, 2: 48, 1: 20, 0: 10}
        score = float(base_scores.get(active_tiers, 10))

        # Bonus: clear single focal point (1–2 hero elements)
        if 1 <= tier_hero <= 2:
            score = min(100.0, score + 10.0)

        # Penalty: too many competing hero-sized elements (no focus)
        if tier_hero > 3:
            score = max(0.0, score - 15.0)

        # Penalty: no mid-level structure at all
        if tier_section == 0 and tier_card == 0:
            score = max(0.0, score - 10.0)

        sub_score = round(score, 1)

        if sub_score >= 85:
            feedback = (f"{active_tiers} size tiers — strong visual hierarchy. "
                        "Clear focal point with well-structured sections and detail layers.")
        elif sub_score >= 65:
            feedback = (f"{active_tiers} size tiers — decent hierarchy. "
                        "Define a stronger primary focal element and add structural sub-sections.")
        elif sub_score >= 40:
            feedback = (f"{active_tiers} size tiers — weak hierarchy. "
                        "Elements are too uniform in size; use intentional scale variation.")
        else:
            feedback = ("Flat layout — no visual hierarchy detected. "
                        "Use size, weight, and spacing to guide the viewer's eye.")

        return {
            "raw_value": active_tiers,
            "sub_score": sub_score,
            "feedback": feedback,
        }

    except Exception as e:
        return {"raw_value": 0, "sub_score": 0,
                "feedback": f"Hierarchy check error: {e}", "error": True}
