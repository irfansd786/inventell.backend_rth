"""Camera calibration: camera-pixel coordinates → 2D store-map coordinates.

Uses a 4-point perspective (homography) transform. Default calibration is a
sensible top-down approximation; per-camera overrides can be stored via
`save_calibration()` and are picked up automatically. Later these points can
be selected interactively in the UI.
"""

import json
import os

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'media', 'calibration.json')

# Default: camera quad (normalized 0..1) -> store map quad (percent 0..100).
DEFAULT_CALIBRATION = {
    'default': {
        'camera': [[0.08, 0.92], [0.92, 0.92], [0.90, 0.18], [0.10, 0.18]],
        'map': [[12.0, 62.0], [82.0, 62.0], [70.0, 14.0], [22.0, 14.0]],
    }
}


def _load_all() -> dict:
    try:
        if os.path.isfile(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, 'r', encoding='utf-8') as fh:
                return json.load(fh)
    except (OSError, ValueError):
        pass
    return {}


def get_calibration(camera_id: str = 'camera_01') -> dict:
    saved = _load_all()
    if camera_id in saved:
        return saved[camera_id]
    return DEFAULT_CALIBRATION['default']


def save_calibration(camera_id: str, camera_points: list, map_points: list) -> dict:
    if len(camera_points) < 4 or len(map_points) < 4:
        raise ValueError('At least 4 calibration point pairs are required')
    saved = _load_all()
    saved[camera_id] = {'camera': camera_points[:4], 'map': map_points[:4]}
    os.makedirs(os.path.dirname(CALIBRATION_FILE), exist_ok=True)
    with open(CALIBRATION_FILE, 'w', encoding='utf-8') as fh:
        json.dump(saved, fh, indent=2)
    return saved[camera_id]


def build_homography(camera_id: str = 'camera_01'):
    """Return the 3x3 homography matrix (camera-normalized -> map percent)."""
    if cv2 is None or np is None:
        return None
    cal = get_calibration(camera_id)
    src = np.array(cal['camera'], dtype=np.float32)
    dst = np.array(cal['map'], dtype=np.float32)
    matrix, _ = cv2.findHomography(src, dst)
    return matrix


def apply_homography(matrix, x: float, y: float) -> tuple[float, float]:
    if matrix is None or np is None:
        return round(x * 100.0, 1), round(y * 100.0, 1)
    vec = np.array([[[x, y]]], dtype=np.float32)
    mapped = cv2.perspectiveTransform(vec, matrix)
    mx, my = float(mapped[0][0][0]), float(mapped[0][0][1])
    return round(max(0.0, min(100.0, mx)), 1), round(max(0.0, min(100.0, my)), 1)
