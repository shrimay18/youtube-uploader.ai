"""Best-frame picker for Shorts thumbnails.

Samples frames across the video and scores each on sharpness + brightness +
face presence. Returns the highest-scoring frame as a saved image path.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _sharpness(gray: np.ndarray) -> float:
    # Variance of Laplacian — higher = crisper.
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness_score(gray: np.ndarray) -> float:
    # Prefer well-lit but not blown-out frames; peak reward around mid-bright.
    mean = gray.mean() / 255.0
    return 1.0 - abs(mean - 0.55) * 2  # 1.0 at 0.55, falls off toward extremes


def _load_cascade():
    """Return a face cascade, or None if this OpenCV build lacks Haar support."""
    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
        return None
    try:
        c = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        return c if not c.empty() else None
    except Exception:
        return None


def _face_score(gray: np.ndarray, cascade) -> float:
    if cascade is None:
        return 0.0
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return 0.0
    # Reward the largest face's relative area (a clear subject reads well as a thumb).
    biggest = max(faces, key=lambda f: f[2] * f[3])
    h, w = gray.shape
    return min(1.0, (biggest[2] * biggest[3]) / (w * h) * 6)


def best_frame(video_path: Path, out_path: Path, samples: int = 40) -> Path:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    cascade = _load_cascade()

    # Skip the first/last 8% (intros/outros are rarely good thumbs).
    lo, hi = int(total * 0.08), int(total * 0.92) if total else 0
    if total <= 0 or hi <= lo:
        indices = list(range(0, max(1, total), max(1, total // samples or 1)))
    else:
        indices = np.linspace(lo, hi, samples, dtype=int).tolist()

    best_score, best_img = -1.0, None
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharp = _sharpness(gray)
        sharp_norm = min(1.0, sharp / 500.0)     # ~500 var is already crisp
        score = 0.5 * sharp_norm + 0.2 * _brightness_score(gray) + 0.3 * _face_score(gray, cascade)
        if score > best_score:
            best_score, best_img = score, frame

    cap.release()
    if best_img is None:
        raise RuntimeError("No readable frames found for thumbnail selection.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), best_img)
    return out_path
