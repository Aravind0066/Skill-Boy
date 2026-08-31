"""
SkillBlade Referee — Core Evaluator
=====================================

Scoring Pipeline (per user spec):
  1. Each module outputs: raw_value + sub_score (0-100)
  2. Weighted average of sub_scores → design_craft_score (0-100)
  3. design_craft_score scaled into points → design_craft_points (0 to MAX_POINTS)

Module weights (sum to 1.0):
  Contrast      → 0.30  (most impactful for readability)
  Grid          → 0.25  (layout structure)
  Color Palette → 0.20  (visual discipline)
  Spacing       → 0.15  (rhythm)
  Buttons       → 0.10  (component consistency)
"""

import os
from modules.contrast_checker    import evaluate_contrast
from modules.color_palette        import evaluate_colors
from modules.grid_alignment       import evaluate_grid
from modules.spacing_rhythm       import evaluate_spacing
from modules.button_consistency   import evaluate_buttons

# ── Configurable weights ──────────────────────────────────────────────────────
WEIGHTS = {
    "contrast":  0.30,
    "grid":      0.25,
    "colors":    0.20,
    "spacing":   0.15,
    "buttons":   0.10,
}

# Max points in the bigger 100-pt rubric allocated to Design & Craft
MAX_POINTS = 20

# ─────────────────────────────────────────────────────────────────────────────

def get_tier(score):
    """Map final 0-100 score to a SkillBlade tier."""
    if score >= 85:   return ("Elite",        "🏆", "elite")
    elif score >= 80: return ("Rider",         "🚀", "rider")
    elif score >= 75: return ("Blader Rider",  "⚡", "blader-rider")
    elif score >= 50: return ("Blader",        "🔰", "blader")
    else:             return ("Rejected",      "❌", "rejected")

def tier_description(tier_name):
    descs = {
        "Elite":        "Top-tier execution. Professional-grade design craft.",
        "Rider":        "Solid foundation. A few tweaks away from Elite.",
        "Blader Rider": "Decent base, but key areas need attention.",
        "Blader":       "Needs significant improvement before submission.",
        "Rejected":     "Design fundamentals are not met. Start over.",
    }
    return descs.get(tier_name, "")

def evaluate_screenshot(image_path):
    """
    Main entry point. Runs all modules, computes weighted score, returns full result dict.
    """
    if not os.path.exists(image_path):
        return {"error": "Uploaded file not found on server."}

    # ── Run all modules ──────────────────────────────────────────────────────
    results_raw = {
        "contrast": evaluate_contrast(image_path),
        "grid":     evaluate_grid(image_path),
        "colors":   evaluate_colors(image_path),
        "spacing":  evaluate_spacing(image_path),
        "buttons":  evaluate_buttons(image_path),
    }

    # ── Weighted average of sub_scores (0-100) ───────────────────────────────
    design_craft_score = sum(
        results_raw[k]["sub_score"] * WEIGHTS[k]
        for k in WEIGHTS
    )
    design_craft_score = round(design_craft_score, 1)

    # ── Scale to points in the larger rubric ────────────────────────────────
    design_craft_points = round((design_craft_score / 100) * MAX_POINTS, 1)

    # ── Tier ─────────────────────────────────────────────────────────────────
    tier_name, tier_icon, tier_key = get_tier(design_craft_score)

    # ── Build human-friendly module list ────────────────────────────────────
    module_display = [
        {
            "key": "contrast",
            "label": "Contrast Ratio",
            "weight_pct": int(WEIGHTS["contrast"] * 100),
            "sub_score": results_raw["contrast"]["sub_score"],
            "raw_display": f"{results_raw['contrast']['raw_value']}:1",
            "raw_label": "WCAG Ratio",
            "feedback": results_raw["contrast"]["feedback"],
        },
        {
            "key": "grid",
            "label": "Grid Alignment",
            "weight_pct": int(WEIGHTS["grid"] * 100),
            "sub_score": results_raw["grid"]["sub_score"],
            "raw_display": str(results_raw["grid"]["raw_value"]),
            "raw_label": "Alignment Lines",
            "feedback": results_raw["grid"]["feedback"],
        },
        {
            "key": "colors",
            "label": "Color Palette",
            "weight_pct": int(WEIGHTS["colors"] * 100),
            "sub_score": results_raw["colors"]["sub_score"],
            "raw_display": str(results_raw["colors"]["raw_value"]),
            "raw_label": "Dominant Colors",
            "feedback": results_raw["colors"]["feedback"],
        },
        {
            "key": "spacing",
            "label": "Spacing Rhythm",
            "weight_pct": int(WEIGHTS["spacing"] * 100),
            "sub_score": results_raw["spacing"]["sub_score"],
            "raw_display": f"{results_raw['spacing']['raw_value']}%",
            "raw_label": "Rhythmic Gaps",
            "feedback": results_raw["spacing"]["feedback"],
        },
        {
            "key": "buttons",
            "label": "Button Consistency",
            "weight_pct": int(WEIGHTS["buttons"] * 100),
            "sub_score": results_raw["buttons"]["sub_score"],
            "raw_display": f"{results_raw['buttons']['raw_value']}%",
            "raw_label": "Height Variance",
            "feedback": results_raw["buttons"]["feedback"],
        },
    ]

    # ── Weaknesses (sub_score < 65) ──────────────────────────────────────────
    weaknesses = [m for m in module_display if m["sub_score"] < 65]
    strengths  = [m for m in module_display if m["sub_score"] >= 80]

    return {
        "design_craft_score": design_craft_score,   # 0-100 quality score
        "design_craft_points": design_craft_points,  # e.g. 14.5 / 20
        "max_points": MAX_POINTS,
        "tier_name": tier_name,
        "tier_icon": tier_icon,
        "tier_key":  tier_key,
        "tier_desc": tier_description(tier_name),
        "modules":   module_display,
        "weaknesses": weaknesses,
        "strengths":  strengths,
    }
