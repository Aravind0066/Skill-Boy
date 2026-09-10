"""
SkillBlade Referee — Core Evaluator
=====================================

Scoring Pipeline (per user spec):
  1. Each module outputs: raw_value + sub_score (0-100)
  2. Weighted average of sub_scores → design_craft_score (0-100)
  3. design_craft_score scaled into points → design_craft_points (0 to MAX_POINTS)

Module weights (sum = 1.0):
  Contrast        → 0.20  (Morphological Text-Region Isolation)
  Visual Hierarchy→ 0.15  (Size tiers & focal point)
  Grid Alignment  → 0.15  (2D Spatial Grids - Rows & Columns)
  Visual Balance  → 0.15  (Macro Whitespace Density)
  Color Palette   → 0.15  (Palette control & saturation discipline)
  Spacing Rhythm  → 0.12  (8px grid adherence + gap consistency)
  Button/Component→ 0.08  (Component uniformity)

Tier thresholds (stricter for professional screening):
  Elite        ≥ 88  — Portfolio-ready, clear hire signal
  Rider        ≥ 76  — Strong work, minor polish needed
  Blader Rider ≥ 62  — Decent base with clear weak areas
  Blader       ≥ 44  — Needs significant rework
  Rejected      < 44  — Design fundamentals not met
"""

import os
from modules.contrast_checker   import evaluate_contrast
from modules.visual_hierarchy   import evaluate_hierarchy
from modules.grid_alignment     import evaluate_grid
from modules.color_palette      import evaluate_colors
from modules.spacing_rhythm     import evaluate_spacing
from modules.button_consistency import evaluate_buttons
from modules.visual_balance     import evaluate_balance

# ── Visual-judge weights (must sum to 1.0) ───────────────────────────────────
# Structure and clarity carry more weight than any single pixel-level signal.
# Contrast remains important, but strong edges alone should not produce an
# elite result without hierarchy, composition, rhythm, and consistency.
WEIGHTS = {
    "contrast":   0.12,
    "hierarchy":  0.20,
    "grid":       0.18,
    "balance":    0.15,
    "colors":     0.12,
    "spacing":    0.13,
    "buttons":    0.10,
}

# Max points in the bigger 100-pt rubric allocated to Design & Craft
MAX_POINTS = 20

# ─────────────────────────────────────────────────────────────────────────────


def get_tier(score):
    """Map final 0-100 score to a SkillBlade tier (stricter thresholds)."""
    if score >= 88:   return ("Elite",        "🏆", "elite")
    elif score >= 76: return ("Rider",         "🚀", "rider")
    elif score >= 62: return ("Blader Rider",  "⚡", "blader-rider")
    elif score >= 44: return ("Blader",        "🔰", "blader")
    else:             return ("Rejected",      "❌", "rejected")


def tier_description(tier_name):
    descs = {
        "Elite":        "Portfolio-ready execution. This is the standard for professional hire.",
        "Rider":        "Strong design fundamentals. A few targeted improvements away from Elite.",
        "Blader Rider": "Solid base, but key areas (hierarchy, contrast, or grid) need attention.",
        "Blader":       "Design fundamentals present but applied inconsistently. Significant rework needed.",
        "Rejected":     "Core design principles are not met. Revisit layout, contrast, and color from scratch.",
    }
    return descs.get(tier_name, "")


def evaluate_screenshot(image_path):
    """
    Main entry point. Runs all modules, computes weighted score, returns full result dict.
    Results are fully deterministic — identical image always produces identical scores.
    """
    if not os.path.exists(image_path):
        return {"error": "Uploaded file not found on server."}

    # ── Run all modules ───────────────────────────────────────────────────────
    results_raw = {
        "contrast":  evaluate_contrast(image_path),
        "hierarchy": evaluate_hierarchy(image_path),
        "grid":      evaluate_grid(image_path),
        "balance":   evaluate_balance(image_path),
        "colors":    evaluate_colors(image_path),
        "spacing":   evaluate_spacing(image_path),
        "buttons":   evaluate_buttons(image_path),
    }

    # ── Weighted average of sub_scores (0-100) ────────────────────────────────
    design_craft_score = sum(
        results_raw[k]["sub_score"] * WEIGHTS[k]
        for k in WEIGHTS
    )
    design_craft_score = round(design_craft_score, 1)

    # ── Scale to points in the larger rubric ──────────────────────────────────
    design_craft_points = round((design_craft_score / 100) * MAX_POINTS, 1)

    # ── Tier ──────────────────────────────────────────────────────────────────
    tier_name, tier_icon, tier_key = get_tier(design_craft_score)

    # ── Build human-friendly module list ──────────────────────────────────────
    module_display = [
        {
            "key":        "contrast",
            "label":      "Visual Design & Contrast",
            "sub_metrics": ["foreground/background separation", "readability signal"],
            "weight_pct": int(WEIGHTS["contrast"] * 100),
            "sub_score":  results_raw["contrast"]["sub_score"],
            "raw_display": f"{results_raw['contrast']['raw_value']}:1",
            "raw_label":  "WCAG Ratio",
            "feedback":   results_raw["contrast"]["feedback"],
        },
        {
            "key":        "hierarchy",
            "label":      "Visual Hierarchy",
            "sub_metrics": ["size tiers", "focal prominence", "section differentiation"],
            "weight_pct": int(WEIGHTS["hierarchy"] * 100),
            "sub_score":  results_raw["hierarchy"]["sub_score"],
            "raw_display": f"{results_raw['hierarchy']['raw_value']} tiers",
            "raw_label":  "Size Tiers",
            "feedback":   results_raw["hierarchy"]["feedback"],
        },
        {
            "key":        "grid",
            "label":      "Layout & Composition",
            "sub_metrics": ["horizontal alignment", "vertical alignment", "grid structure"],
            "weight_pct": int(WEIGHTS["grid"] * 100),
            "sub_score":  results_raw["grid"]["sub_score"],
            "raw_display": str(results_raw["grid"]["raw_value"]),
            "raw_label":  "Alignment",
            "feedback":   results_raw["grid"]["feedback"],
        },
        {
            "key":        "balance",
            "label":      "Visual Clarity",
            "sub_metrics": ["content density", "whitespace", "visual clutter"],
            "weight_pct": int(WEIGHTS["balance"] * 100),
            "sub_score":  results_raw["balance"]["sub_score"],
            "raw_display": str(results_raw["balance"]["raw_value"]),
            "raw_label":  "Macro Whitespace",
            "feedback":   results_raw["balance"]["feedback"],
        },
        {
            "key":        "colors",
            "label":      "Color Discipline",
            "sub_metrics": ["palette complexity", "saturation balance", "dominant-color control"],
            "weight_pct": int(WEIGHTS["colors"] * 100),
            "sub_score":  results_raw["colors"]["sub_score"],
            "raw_display": str(results_raw["colors"]["raw_value"]),
            "raw_label":  "Dominant Colors",
            "feedback":   results_raw["colors"]["feedback"],
        },
        {
            "key":        "spacing",
            "label":      "Spacing & Rhythm",
            "sub_metrics": ["gap consistency", "8px rhythm adherence", "vertical spacing"],
            "weight_pct": int(WEIGHTS["spacing"] * 100),
            "sub_score":  results_raw["spacing"]["sub_score"],
            "raw_display": f"{results_raw['spacing']['raw_value']}%",
            "raw_label":  "8px-Rhythmic Gaps",
            "feedback":   results_raw["spacing"]["feedback"],
        },
        {
            "key":        "buttons",
            "label":      "Component Consistency & Polish",
            "sub_metrics": ["repeated component geometry", "button height consistency", "alignment consistency"],
            "weight_pct": int(WEIGHTS["buttons"] * 100),
            "sub_score":  results_raw["buttons"]["sub_score"],
            "raw_display": f"{results_raw['buttons']['raw_value']}%",
            "raw_label":  "Height Variance",
            "feedback":   results_raw["buttons"]["feedback"],
        },
    ]

    # ── Weaknesses (sub_score < 65) and Strengths (sub_score ≥ 80) ───────────
    weaknesses = [m for m in module_display if m["sub_score"] < 65]
    strengths  = [m for m in module_display if m["sub_score"] >= 80]

    return {
        "design_craft_score":  design_craft_score,
        "design_craft_points": design_craft_points,
        "max_points":          MAX_POINTS,
        "tier_name":           tier_name,
        "tier_icon":           tier_icon,
        "tier_key":            tier_key,
        "tier_desc":           tier_description(tier_name),
        "modules":             module_display,
        "weaknesses":          weaknesses,
        "strengths":           strengths,
    }
