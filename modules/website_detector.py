"""Heuristics for deciding whether an image looks like a website UI."""

import cv2
import numpy as np


def detect_website(image_path):
    """Return a conservative website-likelihood score and explainable signals."""
    image = cv2.imread(image_path)
    if image is None:
        return {"is_website": False, "confidence": 0, "signals": ["unreadable image"]}

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / edges.size

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, width // 30), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(12, height // 30)))
    horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
    vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)
    line_density = float(np.count_nonzero(horizontal_lines | vertical_lines)) / edges.size

    signals = []
    confidence = 0
    aspect_ratio = width / max(height, 1)
    if aspect_ratio >= 1.15:
        confidence += 20
        signals.append("landscape layout")
    if 0.015 <= edge_density <= 0.30:
        confidence += 25
        signals.append("structured edges")
    if line_density >= 0.0015:
        confidence += 30
        signals.append("UI-like alignment lines")

    # Web layouts tend to contain both quiet regions and dense component regions.
    blocks = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    if float(np.std(blocks)) >= 18:
        confidence += 25
        signals.append("mixed content density")

    return {
        "is_website": confidence >= 55,
        "confidence": confidence,
        "signals": signals,
        "width": width,
        "height": height,
    }