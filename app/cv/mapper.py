"""Position mapping: detection bbox -> foot point -> store-map coordinates.

The FOOT POINT (bottom-center of the bounding box) is used as the floor
position — far more accurate than the bbox center for top-down mapping.
"""

from app.cv.calibration import apply_homography, build_homography


def foot_point(bbox: list, frame_width: int, frame_height: int) -> tuple[float, float]:
    """Bottom-center of bbox, normalized to 0..1 camera coordinates."""
    x1, y1, x2, y2 = bbox
    fx = ((x1 + x2) / 2.0) / max(frame_width, 1)
    fy = y2 / max(frame_height, 1)
    return round(max(0.0, min(1.0, fx)), 4), round(max(0.0, min(1.0, fy)), 4)


class PositionMapper:
    def __init__(self, camera_id: str = 'camera_01'):
        self.camera_id = camera_id
        self._matrix = build_homography(camera_id)

    def to_map(self, bbox: list, frame_width: int, frame_height: int) -> dict:
        fx, fy = foot_point(bbox, frame_width, frame_height)
        mx, my = apply_homography(self._matrix, fx, fy)
        return {'foot': [fx, fy], 'map': {'x': mx, 'y': my}}
