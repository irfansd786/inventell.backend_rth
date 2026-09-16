"""Offline video processing job.

TEST VIDEO -> OpenCV -> YOLO PERSON detection (class 0 only) -> class
filter -> ByteTrack -> TRACK IDs -> foot point (bottom-center) ->
homography -> 2D coordinates. Results are stored per-timestamp so the
frontend can poll `tracks?timestamp=` in sync with video playback.

Runs in a background thread; progress is observable via `status()`.
Processed results are cached as JSON next to the video so replays are instant.

Camera roles: camera_01 is the PRIMARY person detection/tracking source.
camera_02 is a REFERENCE / CALIBRATION source — each camera has an
independent job and IDs are never merged across cameras.
"""

import json
import logging
import os
import threading
import time

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

from app.cv.calibration import get_calibration
from app.cv.detector import PERSON_CLASS_ID, PERSON_CLASS_NAME, PersonDetector
from app.cv.mapper import PositionMapper
from app.cv.reid import extract_appearance_feature
from app.cv.tracker import IoUTracker, is_person_detection
from app.cv.video_source import UploadedVideoSource
from app.cv.zones import zone_for_point

log = logging.getLogger(__name__)

FRAME_SAMPLE_EVERY = 5
DETECT_WIDTH = 480
# YOLO resolves grouped/occluded people better at higher input resolution.
DETECT_WIDTH_YOLO = 640

# Bump when the cached track schema changes so stale caches (e.g. from
# before the person-only fix) are reprocessed instead of replayed.
CACHE_VERSION = 2


def _debug_enabled() -> bool:
    return os.getenv('DEBUG_DETECTION', 'false').lower() in ('1', 'true', 'yes', 'on')


def _detector_info() -> dict:
    """Honest detector configuration for status displays (env-driven)."""
    model_path = os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt')
    try:
        threshold = float(os.getenv('PERSON_CONFIDENCE_THRESHOLD', '0.40'))
    except ValueError:
        threshold = 0.40
    return {
        'model': os.path.basename(model_path),
        'person_class_id': PERSON_CLASS_ID,
        'person_class_name': PERSON_CLASS_NAME,
        'confidence_threshold': threshold,
        'tracker': 'ByteTrack (IoU association)',
    }


class ProcessingJob:
    def __init__(self, camera_id: str, video_path: str):
        self.camera_id = camera_id
        self.video_path = video_path
        self.cache_path = os.path.splitext(video_path)[0] + '.tracks.json'
        self.state = 'idle'  # idle | processing | ready | error
        self.progress = 0.0
        self.error = ''
        self.engine = 'unavailable'
        self.frames: list = []  # [{t, people:[{id,class_id,class_name,confidence,bbox,foot,map,zone,dwell}]}]
        self.lifecycles: dict = {}  # track_id -> {first_seen,last_seen}
        self.duration = 0.0
        self._thread = None

    # ---------- public API ----------

    def status(self) -> dict:
        return {
            'camera_id': self.camera_id,
            'state': self.state,
            'progress': round(self.progress, 1),
            'error': self.error,
            'engine': self.engine,
            'frames_indexed': len(self.frames),
            'duration': self.duration,
            'calibration': get_calibration(self.camera_id),
            'detector': _detector_info(),
        }

    def start(self, force: bool = False) -> dict:
        if self.state == 'processing':
            return self.status()
        if not force and self._load_cache():
            self.state = 'ready'
            self.progress = 100.0
            return self.status()
        if cv2 is None:
            self.state = 'error'
            self.error = 'OpenCV (cv2) is not installed — detection engine not connected'
            return self.status()
        detector = PersonDetector()
        if not detector.available:
            self.state = 'error'
            self.error = 'No detection engine available (YOLO weights and motion fallback both unavailable)'
            return self.status()
        self.engine = detector.engine
        self.state = 'processing'
        self.progress = 0.0
        self.error = ''
        self._thread = threading.Thread(target=self._run, args=(detector,), daemon=True)
        self._thread.start()
        return self.status()

    def stop(self) -> dict:
        self.state = 'idle' if not self.frames else 'ready'
        return self.status()

    def tracks_at(self, timestamp: float) -> list:
        """People visible at timestamp t — never future positions, persons only."""
        if not self.frames:
            return []
        best = None
        for frame in self.frames:
            if frame['t'] <= timestamp + 1e-6:
                best = frame
            else:
                break
        if best is None:
            return []
        # Defensive person-only filter: never serve non-person cached data.
        return [p for p in best['people'] if self._is_person_row(p)]

    @staticmethod
    def _is_person_row(p: dict) -> bool:
        if p.get('class_id', PERSON_CLASS_ID) != PERSON_CLASS_ID:
            return False
        name = p.get('class_name', PERSON_CLASS_NAME)
        if name is not None and str(name).lower() != PERSON_CLASS_NAME:
            return False
        return True

    # ---------- internals ----------

    @staticmethod
    def _suppress_contained(dets: list, threshold: float = 0.65) -> list:
        """Suppress multi-scale duplicate boxes where one detection is mostly inside another."""
        if len(dets) <= 1:
            return dets
        sorted_dets = sorted(dets, key=lambda d: d.get('confidence', 0), reverse=True)
        kept = []
        for d in sorted_dets:
            x1, y1, x2, y2 = d['bbox']
            area = max(1.0, (x2 - x1) * (y2 - y1))
            suppress = False
            for k in kept:
                kx1, ky1, kx2, ky2 = k['bbox']
                ix1, iy1 = max(x1, kx1), max(y1, ky1)
                ix2, iy2 = min(x2, kx2), min(y2, ky2)
                if ix2 > ix1 and iy2 > iy1:
                    iarea = (ix2 - ix1) * (iy2 - iy1)
                    if (iarea / area) > threshold:
                        suppress = True
                        break
            if not suppress:
                kept.append(d)
        return kept

    @staticmethod
    def _merge_nearby(dets: list, gap: float = 40.0) -> list:
        """Merge boxes whose edges are within `gap` px (split silhouettes)."""
        boxes = [dict(d) for d in dets]
        merged = True
        while merged:
            merged = False
            out = []
            used = [False] * len(boxes)
            for i, a in enumerate(boxes):
                if used[i]:
                    continue
                ax1, ay1, ax2, ay2 = a['bbox']
                for j in range(i + 1, len(boxes)):
                    if used[j]:
                        continue
                    bx1, by1, bx2, by2 = boxes[j]['bbox']
                    x_gap = max(bx1 - ax2, ax1 - bx2)
                    y_gap = max(by1 - ay2, ay1 - by2)
                    if x_gap < gap and y_gap < gap * 2:
                        ax1, ay1 = min(ax1, bx1), min(ay1, by1)
                        ax2, ay2 = max(ax2, bx2), max(ay2, by2)
                        a['confidence'] = round(max(a['confidence'], boxes[j]['confidence']), 3)
                        used[j] = True
                        merged = True
                a['bbox'] = [ax1, ay1, ax2, ay2]
                out.append(a)
                used[i] = True
            boxes = out
        return boxes

    def _load_cache(self) -> bool:
        try:
            if not os.path.isfile(self.cache_path):
                return False
            with open(self.cache_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get('version', 1) < CACHE_VERSION:
                return False  # stale schema — reprocess with person-only pipeline
            frames = data.get('frames', [])
            if not frames:
                return False
            # Stale person-schema check: every row must be class 0/person.
            for frame in frames[:5]:
                for p in frame.get('people', [])[:5]:
                    if not self._is_person_row(p):
                        return False
            self.frames = frames
            self.lifecycles = {int(k): v for k, v in data.get('lifecycles', {}).items()}
            self.duration = data.get('duration', 0.0)
            self.engine = data.get('engine', 'hog')
            return bool(self.frames)
        except (OSError, ValueError):
            return False

    def _save_cache(self):
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as fh:
                json.dump(
                    {
                        'version': CACHE_VERSION,
                        'frames': self.frames,
                        'lifecycles': self.lifecycles,
                        'duration': self.duration,
                        'engine': self.engine,
                    },
                    fh,
                )
        except OSError:
            pass

    def _run(self, detector: PersonDetector):
        try:
            source = UploadedVideoSource(self.video_path).open()
        except Exception as exc:
            self.state = 'error'
            self.error = str(exc)
            return
        try:
            meta = source.metadata()
            self.duration = meta.get('duration', 0.0)
            total = max(meta.get('frames', 1), 1)
            mapper = PositionMapper(self.camera_id)
            tracker = IoUTracker()
            fw = meta.get('width', 640) or 640
            fh = meta.get('height', 360) or 360
            detect_width = DETECT_WIDTH_YOLO if detector.engine == 'yolo' else DETECT_WIDTH
            scale = detect_width / max(fw, 1)
            dw, dh = int(fw * scale), int(fh * scale)

            frames_out = []
            lifecycles = {}
            idx = 0
            while True:
                item = source.read()
                if item is None:
                    break
                frame, t = item
                idx += 1
                if (idx - 1) % FRAME_SAMPLE_EVERY != 0:
                    continue
                small = cv2.resize(frame, (dw, dh))
                dets = detector.detect(small)
                # Scale bboxes back to source resolution.
                for det in dets:
                    det['bbox'] = [c / scale for c in det['bbox']]
                # Backend safety filter (layer 1): non-person detections are
                # discarded BEFORE merging/tracking and can never get an ID.
                raw_count = len(dets)
                dets = [d for d in dets if is_person_detection(d)]
                rejected_prefilter = raw_count - len(dets)
                # NOTE: _merge_nearby runs ONLY for the motion fallback (where one
                # person can split into fragments). YOLO boxes are already NMS'd —
                # merging them would fuse 2-3 grouped people into a single ID.
                if detector.engine == 'yolo':
                    dets = self._suppress_contained(dets, threshold=0.65)
                else:
                    dets = self._merge_nearby(dets, gap=40.0)
                tracks = tracker.update(dets, round(t, 2))
                people = []
                for track in tracker.active_tracks():
                    # Backend safety filter (layer 2): belt-and-braces check.
                    if track.class_id != PERSON_CLASS_ID:
                        continue
                    mapped = mapper.to_map(track.bbox, fw, fh)
                    zone = zone_for_point(mapped['map']['x'], mapped['map']['y'])
                    lifecycles[track.id] = {'first_seen': track.first_seen, 'last_seen': track.last_seen}
                    feat = extract_appearance_feature(frame, track.bbox)
                    people.append(
                        {
                            'id': track.id,
                            'class_id': PERSON_CLASS_ID,
                            'class_name': PERSON_CLASS_NAME,
                            'confidence': round(track.confidence, 3),
                            'bbox': [round(c, 1) for c in track.bbox],
                            'frame': {'width': fw, 'height': fh},
                            'foot': mapped['foot'],
                            'map': mapped['map'],
                            'zone': zone['id'] if zone else 'aisle',
                            'zone_name': zone['name'] if zone else 'Aisle',
                            'dwell': track.dwell,
                            'timestamp': round(t, 2),
                            'feature': feat,
                        }
                    )
                frames_out.append({'t': round(t, 2), 'people': people})
                if _debug_enabled():
                    stats = getattr(detector, 'last_stats', {}) or {}
                    active_ids = sorted(p['id'] for p in people)
                    log.debug(
                        '[DETECT] frame=%.1fs raw_yolo=%s persons=%d rejected=%s '
                        'active_ids=%s',
                        t, stats.get('raw', raw_count), len(people),
                        stats.get('rejected', rejected_prefilter), active_ids,
                    )
                self.progress = min(99.0, idx / total * 100.0)
                if idx % 50 == 0:
                    time.sleep(0)
            self.frames = frames_out
            self.lifecycles = lifecycles
            self._save_cache()
            self.state = 'ready'
            self.progress = 100.0
        except Exception as exc:
            self.state = 'error'
            self.error = f'Processing failed: {exc}'
        finally:
            source.release()
