"""
Shared deterministic K-Means utility for SkillBlade modules.

OpenCV's cv2.kmeans uses its own internal C++ RNG that ignores np.random.seed,
making results non-deterministic even with KMEANS_PP_CENTERS.

This module implements a lightweight K-Means in pure NumPy that is fully
deterministic: initial centers are chosen by evenly sampling the sorted pixel
array — no randomness involved.
"""

import numpy as np


def _init_centers_deterministic(pixels: np.ndarray, k: int) -> np.ndarray:
    """
    Pick k initial centers by sampling evenly from brightness-sorted pixels.
    Fully deterministic — no RNG.
    """
    # Sort pixels by their L2 norm (brightness proxy) for canonical ordering
    order = np.argsort(np.linalg.norm(pixels, axis=1))
    sorted_pixels = pixels[order]
    # Evenly spaced indices across the sorted array
    indices = np.linspace(0, len(sorted_pixels) - 1, k, dtype=int)
    return sorted_pixels[indices].copy()


def kmeans_deterministic(pixels: np.ndarray, k: int,
                          max_iter: int = 30,
                          tol: float = 0.5) -> tuple:
    """
    Deterministic K-Means clustering.

    Args:
        pixels   : (N, D) float32 array
        k        : number of clusters
        max_iter : maximum iterations
        tol      : convergence tolerance (centroid shift)

    Returns:
        labels   : (N,) int32 array of cluster assignments
        centers  : (k, D) float32 array of final centroids
    """
    centers = _init_centers_deterministic(pixels, k)

    for _ in range(max_iter):
        # Assign each pixel to nearest center
        diffs = pixels[:, np.newaxis, :] - centers[np.newaxis, :, :]   # (N, k, D)
        dists = np.sum(diffs ** 2, axis=2)                              # (N, k)
        labels = np.argmin(dists, axis=1).astype(np.int32)

        # Recompute centroids
        new_centers = np.zeros_like(centers)
        for i in range(k):
            mask = labels == i
            if mask.any():
                new_centers[i] = pixels[mask].mean(axis=0)
            else:
                # Empty cluster — reinitialize to a random pixel (deterministic: use median)
                new_centers[i] = centers[i]

        # Check convergence
        shift = np.linalg.norm(new_centers - centers)
        centers = new_centers
        if shift < tol:
            break

    return labels, centers
