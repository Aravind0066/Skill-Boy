"""
SkillBlade Referee — Video Frame Extractor
============================================

Extracts evenly-spaced frames from a video file using OpenCV.
Returns a list of NumPy arrays (BGR images) ready for the heuristic pipeline.
"""

import cv2
import numpy as np
from typing import List, Tuple


def extract_frames(
    video_path: str,
    target_fps: float = 1.0,
    max_frames: int = 20,
) -> Tuple[List[np.ndarray], dict]:
    """
    Extract frames from a video file.

    Args:
        video_path:  Path to the video file (mp4, webm, avi).
        target_fps:  How many frames per second to sample.
        max_frames:  Hard cap on total frames returned.

    Returns:
        (frames, meta)
        frames: list of BGR NumPy arrays
        meta:   dict with video_fps, total_frames, duration_s, sampled_count
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    video_fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s   = total_frames / video_fps if video_fps > 0 else 0

    # Calculate the interval between sampled frames
    interval = max(1, int(round(video_fps / target_fps)))

    frames: List[np.ndarray] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % interval == 0:
            frames.append(frame)
            if len(frames) >= max_frames:
                break
        frame_idx += 1

    cap.release()

    meta = {
        "video_fps":    round(video_fps, 1),
        "total_frames": total_frames,
        "duration_s":   round(duration_s, 1),
        "sampled_count": len(frames),
    }

    return frames, meta
