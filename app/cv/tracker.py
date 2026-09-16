"""Multi-person tracking with stable temporary IDs.

Person-only ByteTrack-style tracker: the video processor only calls
``update(detections, timestamp)`` and reads ``active_tracks()``. Only
detections with ``class_id == 0`` / ``class_name == 'person'`` are accepted —
chairs, tables, bags and any other class are discarded BEFORE association,
so they can never receive a tracking ID.

IDs are persistent while a person is visible (IoU association with a
centroid-distance fallback for sampled frames, plus a grace period). A new
ID is issued only after ``max_missed`` consecutive misses, so brief
occlusions keep the same person ID instead of fragmenting 101 -> 105 -> 110.
"""

from app.cv.detector import PERSON_CLASS_ID, PERSON_CLASS_NAME, PersonDetector


def is_person_detection(det: dict) -> bool:
    """Backend safety filter: True only for COCO PERSON detections."""
    if not isinstance(det, dict):
        return False
    if det.get('class_id', PERSON_CLASS_ID) != PERSON_CLASS_ID:
        return False
    name = det.get('class_name', PERSON_CLASS_NAME)
    if name is not None and str(name).lower() != PERSON_CLASS_NAME:
        return False
    return True


class Track:
    def __init__(self, track_id: int, bbox: list, confidence: float, t: float):
        self.id = track_id
        self.bbox = bbox
        self.confidence = confidence
        self.class_id = PERSON_CLASS_ID
        self.class_name = PERSON_CLASS_NAME
        self.first_seen = t
        self.last_seen = t
        self.missed = 0

    @property
    def dwell(self) -> float:
        return round(self.last_seen - self.first_seen, 1)

    def to_dict(self) -> dict:
        x1, y1, x2, y2 = self.bbox
        return {
            'track_id': self.id,
            'class_id': self.class_id,
            'class_name': self.class_name,
            'confidence': round(float(self.confidence), 3),
            'bbox': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2},
            'foot_point': {'x': round((x1 + x2) / 2.0, 1), 'y': round(y2, 1)},
        }


class IoUTracker:
    """Lightweight IoU tracker (ByteTrack-style association), person-only."""

    def __init__(self, iou_threshold: float = 0.15, max_missed: int = 45,
                 max_centroid_dist: float = 140.0):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.max_centroid_dist = max_centroid_dist
        self._tracks: list[Track] = []
        self._next_id = 101

    @staticmethod
    def _centroid(bbox: list) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def update(self, detections: list, t: float) -> list[Track]:
        # Backend safety filter: non-person detections never enter ByteTrack.
        dets = [d for d in (detections or []) if is_person_detection(d)]
        dets = sorted(dets, key=lambda d: d.get('confidence', 0), reverse=True)
        matched_tracks = set()
        matched_dets = set()

        # Pass 1: IoU association (stable IDs across frames).
        for di, det in enumerate(dets):
            best, best_iou = None, self.iou_threshold
            for track in self._tracks:
                if track.id in matched_tracks:
                    continue
                iou = PersonDetector._iou(det['bbox'], track.bbox)
                if iou > best_iou:
                    best, best_iou = track, iou
            if best is not None:
                best.bbox = det['bbox']
                best.confidence = det.get('confidence', best.confidence)
                best.last_seen = t
                best.missed = 0
                matched_tracks.add(best.id)
                matched_dets.add(di)

        # Pass 2: centroid-distance fallback for sampled frames where a fast
        # walker has low box overlap but is clearly the same person.
        for di, det in enumerate(dets):
            if di in matched_dets:
                continue
            dcx, dcy = self._centroid(det['bbox'])
            best, best_dist = None, self.max_centroid_dist
            for track in self._tracks:
                if track.id in matched_tracks:
                    continue
                tcx, tcy = self._centroid(track.bbox)
                dist = ((dcx - tcx) ** 2 + (dcy - tcy) ** 2) ** 0.5
                if dist < best_dist:
                    best, best_dist = track, dist
            if best is not None:
                best.bbox = det['bbox']
                best.confidence = det.get('confidence', best.confidence)
                best.last_seen = t
                best.missed = 0
                matched_tracks.add(best.id)
                matched_dets.add(di)

        for di, det in enumerate(dets):
            if di not in matched_dets:
                track = Track(self._next_id, det['bbox'], det.get('confidence', 0.0), t)
                self._next_id += 1
                self._tracks.append(track)
                matched_tracks.add(track.id)

        alive = []
        for track in self._tracks:
            if track.id not in matched_tracks:
                track.missed += 1
            if track.missed <= self.max_missed:
                alive.append(track)
        self._tracks = alive
        return list(self._tracks)

    def active_tracks(self) -> list[Track]:
        # Only currently-visible person tracks (missed == 0).
        return [t for t in self._tracks
                if t.missed == 0 and t.class_id == PERSON_CLASS_ID]

    def all_tracks(self) -> list[Track]:
        return list(self._tracks)


# ByteTrack-compatible alias: swapping in ultralytics' native ByteTrack later
# requires no changes upstream or downstream.
ByteTracker = IoUTracker
