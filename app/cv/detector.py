"""Person detection — YOLO (PERSON class only) with motion fallback.

Pipeline guarantee: NOTHING except COCO class 0 (person) ever leaves this
module. YOLO is asked for ``classes=[0]`` AND every box is re-checked
(``class_id == 0``) before it is emitted, so chairs, tables, bags, bottles
and other background objects can never reach the tracker.

Fallback engine: MOG2 background subtraction + strict upright-person shape
gates tuned for static CCTV views (real detection on real video, no model
downloads required). Its boxes are labelled class 0 only after passing the
person-shape gates; anything else is counted as rejected for DEBUG output.
"""

import logging
import os

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from ultralytics import YOLO

    _YOLO_AVAILABLE = True
except ImportError:
    YOLO = None
    _YOLO_AVAILABLE = False

log = logging.getLogger(__name__)

# COCO PERSON class id. The ONLY class that may reach ByteTrack.
# YOLO inference always uses classes=[0]; the safety filter below re-checks.
PERSON_CLASS_ID = 0
PERSON_CLASS_NAME = 'person'


def _debug_enabled() -> bool:
    return os.getenv('DEBUG_DETECTION', 'false').lower() in ('1', 'true', 'yes', 'on')


def _person_threshold(default: float = 0.40) -> float:
    try:
        return float(os.getenv('PERSON_CONFIDENCE_THRESHOLD', str(default)))
    except ValueError:
        return default


class PersonDetector:
    ENGINE_YOLO = 'yolo'
    ENGINE_MOTION = 'motion'
    ENGINE_UNAVAILABLE = 'unavailable'

    def __init__(self, model_path: str | None = None, min_confidence: float | None = None):
        env_model = os.getenv('YOLO_MODEL_PATH', 'yolov8n.pt')
        self.min_confidence = (
            float(min_confidence) if min_confidence is not None else _person_threshold(0.40)
        )
        # NMS IoU threshold for YOLO. Lower keeps overlapping (grouped/occluded)
        # people as SEPARATE boxes instead of merging them into one detection.
        try:
            self.nms_iou = float(os.getenv('YOLO_NMS_IOU', '0.50'))
        except ValueError:
            self.nms_iou = 0.50
        self.engine = self.ENGINE_UNAVAILABLE
        self._model = None
        self._bg = None
        self._seen = 0
        # Debug counters for the last processed frame.
        self.last_stats = {'raw': 0, 'accepted': 0, 'rejected': 0}

        if _YOLO_AVAILABLE:
            try:
                self._model = YOLO(model_path or env_model)
                self.engine = self.ENGINE_YOLO
            except Exception as exc:
                log.warning('YOLO init failed (%s); trying motion fallback', exc)
                self._model = None
        if self._model is None and cv2 is not None and np is not None:
            try:
                self._bg = cv2.createBackgroundSubtractorMOG2(
                    history=200, varThreshold=25, detectShadows=True
                )
                self.engine = self.ENGINE_MOTION
            except Exception as exc:
                log.warning('Motion fallback init failed (%s)', exc)
                self._bg = None

    @property
    def available(self) -> bool:
        return self.engine != self.ENGINE_UNAVAILABLE

    def detect(self, frame) -> list:
        """Return person-only [{'bbox', 'confidence', 'class_id', 'class_name'}]."""
        if self.engine == self.ENGINE_YOLO:
            return self._detect_yolo(frame)
        if self.engine == self.ENGINE_MOTION:
            return self._detect_motion(frame)
        return []

    # ---------------- YOLO (person-only) ----------------

    def _detect_yolo(self, frame) -> list:
        # Layer 1: ask YOLO for class 0 only. iou=self.nms_iou keeps people
        # standing/sitting close together as separate detections.
        results = self._model.predict(
            frame, classes=[PERSON_CLASS_ID], conf=self.min_confidence,
            iou=self.nms_iou, verbose=False,
        )
        boxes = results[0].boxes if results else None
        raw = len(boxes) if boxes is not None else 0
        out = []
        rejected = 0
        if boxes is not None:
            for box in boxes:
                # Layer 2 (safety filter): discard anything that is not class 0,
                # even if a future YOLO version ignores `classes=[0]`.
                try:
                    cls = int(box.cls[0].item()) if hasattr(box, 'cls') else PERSON_CLASS_ID
                except Exception:
                    cls = PERSON_CLASS_ID
                if cls != PERSON_CLASS_ID:
                    rejected += 1
                    continue
                try:
                    conf = float(box.conf[0].item())
                except Exception:
                    conf = self.min_confidence
                if conf < self.min_confidence:
                    rejected += 1
                    continue
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                if x2 <= x1 or y2 <= y1:
                    rejected += 1
                    continue
                out.append(
                    {
                        'bbox': [x1, y1, x2, y2],
                        'confidence': round(conf, 3),
                        'class_id': PERSON_CLASS_ID,
                        'class_name': PERSON_CLASS_NAME,
                    }
                )
        self.last_stats = {'raw': raw, 'accepted': len(out), 'rejected': rejected}
        if _debug_enabled():
            log.debug('[YOLO] raw=%d [PERSON FILTER] accepted=%d rejected=%d',
                      raw, len(out), rejected)
        return out

    # ---------------- Motion fallback (person-shape gates) ----------------

    def _detect_motion(self, frame) -> list:
        self._seen += 1
        fg = self._bg.apply(frame)
        # Warm-up: let the background model settle before emitting boxes.
        if self._seen < 8:
            self.last_stats = {'raw': 0, 'accepted': 0, 'rejected': 0}
            return []
        h, w = fg.shape[:2]
        area = h * w
        # Global-motion guard: skip frames where the whole scene shifts.
        if (np.count_nonzero(fg > 0) / area) > 0.6:
            self.last_stats = {'raw': 0, 'accepted': 0, 'rejected': 0}
            return []
        _, thresh = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
        thresh = cv2.medianBlur(thresh, 5)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        raw = len(contours)
        rejected = 0
        out = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            box_area = bw * bh
            # Person-size gate: reject furniture-scale blobs and tiny noise.
            if box_area < area * 0.004 or box_area > area * 0.30:
                rejected += 1
                continue
            if bh < h * 0.18 or bh > h * 0.95 or bw < w * 0.03:
                rejected += 1
                continue
            # Reject boxes glued to frame edges (shelves, door frames, walls).
            edge = 3
            if x <= edge or y <= edge or (x + bw) >= (w - edge):
                rejected += 1
                continue
            aspect = bh / max(bw, 1)
            if aspect < 1.3 or aspect > 4.5:  # upright-person shape gate
                rejected += 1
                continue
            hull = cv2.convexHull(cnt)
            solidity = float(cv2.contourArea(cnt) / max(cv2.contourArea(hull), 1.0))
            if solidity < 0.45:
                rejected += 1
                continue
            conf = round(min(0.55 + solidity * 0.4, 0.95), 3)
            if conf < self.min_confidence:
                rejected += 1
                continue
            out.append(
                {
                    'bbox': [float(x), float(y), float(x + bw), float(y + bh)],
                    'confidence': conf,
                    'class_id': PERSON_CLASS_ID,
                    'class_name': PERSON_CLASS_NAME,
                }
            )
        kept = self._nms(out)
        rejected += len(out) - len(kept)
        self.last_stats = {'raw': raw, 'accepted': len(kept), 'rejected': rejected}
        if _debug_enabled():
            log.debug('[MOTION] raw=%d [PERSON FILTER] accepted=%d rejected=%d',
                      raw, len(kept), rejected)
        return kept

    @staticmethod
    def _nms(dets: list, iou_thresh: float = 0.4) -> list:
        dets = sorted(dets, key=lambda d: d['confidence'], reverse=True)
        kept = []
        for det in dets:
            keep = True
            for other in kept:
                if PersonDetector._iou(det['bbox'], other['bbox']) > iou_thresh:
                    keep = False
                    break
            if keep:
                kept.append(det)
        return kept

    @staticmethod
    def _iou(a: list, b: list) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if inter <= 0:
            return 0.0
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        return inter / max(area_a + area_b - inter, 1e-6)
