"""Cross-Camera Person Re-Identification (Re-ID) & Global Identity Manager.

Pipeline:
Camera 01: YOLO person detection -> ByteTrack -> Camera Track ID (e.g. C1-103)
Camera 02: YOLO person detection -> ByteTrack -> Camera Track ID (e.g. C2-108)
   │
   ▼
Cross-Camera Matching Engine (app/cv/reid.py):
 1. Appearance Matching: Anonymous multi-part HSV clothing color histograms (no face recognition).
 2. Spatial Consistency: 2D store coordinates mapped via homography.
 3. Temporal Alignment: Simultaneous co-presence & transition handover velocity check.
 4. Zone Transition: Store floor adjacency and travel path validation.
 5. Confidence Gating: Combined score >= threshold (default 0.70 - 0.75).
   │
   ▼
Unified Global Person ID (e.g. GLOBAL 001) -> Store-Level Deduplicated Analytics.
"""

import logging
import os
from collections import defaultdict
from typing import Any

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

log = logging.getLogger(__name__)

# Configurable match confidence threshold (env-driven with strict default)
DEFAULT_REID_THRESHOLD = float(os.getenv('REID_CONFIDENCE_THRESHOLD', '0.55'))
MAX_SPATIAL_DISTANCE_PERCENT = float(os.getenv('REID_MAX_SPATIAL_PERCENT', '35.0'))
MAX_HANDOVER_GAP_SECONDS = float(os.getenv('REID_MAX_HANDOVER_GAP', '10.0'))
MAX_WALKING_SPEED_PERCENT_SEC = 15.0  # ~2.5 m/s in store percent units


# Store zone adjacency matrix (for zone transition plausibility)
ADJACENT_ZONES = {
    'aisle': {'checkout', 'grocery', 'personal', 'snacks', 'beverages', 'entrance'},
    'checkout': {'aisle', 'entrance'},
    'grocery': {'aisle', 'beverages'},
    'personal': {'aisle', 'snacks'},
    'snacks': {'aisle', 'personal', 'beverages'},
    'beverages': {'aisle', 'grocery', 'snacks'},
    'entrance': {'aisle', 'checkout'},
}


def extract_appearance_feature(frame: Any, bbox: list) -> list[float]:
    """Extract anonymous HSV clothing color feature from person bbox.

    Strict Privacy Guarantee:
    - Zero facial recognition or biometric identification.
    - Uses upper torso (clothing shirt/jacket) and lower torso (pants/skirt)
      color histograms normalized to unit Euclidean length.
    """
    if cv2 is None or np is None or frame is None or not bbox or len(bbox) < 4:
        return [0.0] * 32

    fh, fw = frame.shape[:2]
    x1, y1, x2, y2 = [int(round(c)) for c in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(fw, x2), min(fh, y2)

    box_w = x2 - x1
    box_h = y2 - y1
    if box_w < 6 or box_h < 12:
        return [0.0] * 32

    crop = frame[y1:y2, x1:x2]
    ch, cw = crop.shape[:2]

    # Upper torso: 15% to 55% of height (strictly clothing, avoids head/hair)
    upper_crop = crop[int(ch * 0.15):int(ch * 0.55), :]
    # Lower torso: 55% to 95% of height (pants / lower clothing)
    lower_crop = crop[int(ch * 0.55):int(ch * 0.95), :]

    parts_hist = []
    for part in (upper_crop, lower_crop):
        if part.size == 0 or part.shape[0] < 3 or part.shape[1] < 3:
            parts_hist.extend([0.0] * 16)
            continue
        try:
            hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
            # 8 Hue bins [0..180], 2 Saturation bins [0..256] -> 16 bins
            hist = cv2.calcHist([hsv], [0, 1], None, [8, 2], [0, 180, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            parts_hist.extend(hist.tolist())
        except Exception:
            parts_hist.extend([0.0] * 16)

    arr = np.array(parts_hist, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm > 1e-6:
        arr = arr / norm
    return [round(float(v), 4) for v in arr]


def appearance_similarity(feat1: list[float], feat2: list[float]) -> float:
    """Cosine similarity between two normalized anonymous appearance features."""
    if not feat1 or not feat2 or len(feat1) != len(feat2):
        return 0.0
    if np is None:
        dot = sum(a * b for a, b in zip(feat1, feat2))
        return max(0.0, min(1.0, float(dot)))
    a = np.array(feat1, dtype=np.float32)
    b = np.array(feat2, dtype=np.float32)
    dot = float(np.dot(a, b))
    return max(0.0, min(1.0, dot))


def spatial_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance in store-map percentage coordinates [0..100]."""
    return float(((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5)


def compute_zone_similarity(zones1: set[str], zones2: set[str]) -> float:
    """Evaluate store layout transition plausibility between visited zones."""
    if not zones1 or not zones2:
        return 0.5
    # Direct zone overlap
    if zones1 & zones2:
        return 1.0
    # Check graph adjacency
    for z1 in zones1:
        adj = ADJACENT_ZONES.get(z1, set())
        if any(z2 in adj for z2 in zones2):
            return 0.80
    return 0.35


def compute_cross_camera_match(
    track1: dict,
    track2: dict,
    threshold: float = DEFAULT_REID_THRESHOLD,
) -> dict:
    """Multi-signal match evaluation between two tracks from different cameras.

    Signals:
    1. Appearance (40%): anonymous clothing HSV histogram cosine similarity.
    2. Spatial (35%): 2D homography store-map proximity at shared times or handover.
    3. Temporal (15%): time alignment or handover transition window.
    4. Zone (10%): store floor graph adjacency.
    """
    feat1 = track1.get('feature') or []
    feat2 = track2.get('feature') or []
    s_app = appearance_similarity(feat1, feat2)

    t1_min = track1.get('first_seen', 0.0)
    t1_max = track1.get('last_seen', 0.0)
    t2_min = track2.get('first_seen', 0.0)
    t2_max = track2.get('last_seen', 0.0)

    # Overlap or gap
    overlap = min(t1_max, t2_max) - max(t1_min, t2_min)
    is_simultaneous = overlap >= -0.5

    pos1_by_t = track1.get('positions_by_t', {})
    pos2_by_t = track2.get('positions_by_t', {})

    if is_simultaneous:
        dur1 = max(t1_max - t1_min, 0.5)
        dur2 = max(t2_max - t2_min, 0.5)
        overlap_ratio = min(overlap / dur1, overlap / dur2)
        s_temp = 0.40 + 0.60 * max(0.0, min(1.0, overlap_ratio))
        # Compare spatial distance at overlapping timestamps
        common_ts = set(pos1_by_t.keys()) & set(pos2_by_t.keys())
        if common_ts:
            dists = [
                spatial_distance(pos1_by_t[t][0], pos1_by_t[t][1], pos2_by_t[t][0], pos2_by_t[t][1])
                for t in common_ts
            ]
            avg_dist = float(sum(dists) / len(dists))
        else:
            # Nearest timestamp distance
            t_sample = max(t1_min, t2_min)
            p1 = track1.get('mean_pos', (50.0, 50.0))
            p2 = track2.get('mean_pos', (50.0, 50.0))
            avg_dist = spatial_distance(p1[0], p1[1], p2[0], p2[1])
        s_spatial = max(0.0, 1.0 - (avg_dist / MAX_SPATIAL_DISTANCE_PERCENT))
    else:
        gap = max(t1_min, t2_min) - min(t1_max, t2_max)
        if gap > MAX_HANDOVER_GAP_SECONDS:
            return {
                'confidence': 0.0,
                'is_match': False,
                'signals': {'app': s_app, 'spatial': 0.0, 'temp': 0.0, 'zone': 0.0, 'dist': 999.0},
            }
        s_temp = max(0.0, 1.0 - (gap / MAX_HANDOVER_GAP_SECONDS))

        # Check handover distance & walking velocity
        last_p1 = track1.get('last_pos', (50.0, 50.0))
        first_p2 = track2.get('first_pos', (50.0, 50.0))
        dist = spatial_distance(last_p1[0], last_p1[1], first_p2[0], first_p2[1])
        avg_dist = dist
        velocity = dist / max(gap, 0.5)
        if velocity > MAX_WALKING_SPEED_PERCENT_SEC:
            s_spatial = 0.0
        else:
            s_spatial = max(0.0, 1.0 - (dist / (MAX_SPATIAL_DISTANCE_PERCENT * 1.5)))

    zones1 = set(track1.get('zones', []))
    zones2 = set(track2.get('zones', []))
    s_zone = compute_zone_similarity(zones1, zones2)

    if is_simultaneous:
        # For simultaneous co-presence, appearance & spatial proximity dominate
        w_app, w_spatial, w_temp, w_zone = 0.40, 0.30, 0.20, 0.10
        id_bonus = 0.08 if track1.get('id') is not None and track1.get('id') == track2.get('id') else 0.0
    else:
        w_app, w_spatial, w_temp, w_zone = 0.40, 0.30, 0.20, 0.10
        id_bonus = 0.0

    raw_conf = w_app * s_app + w_spatial * s_spatial + w_temp * s_temp + w_zone * s_zone + id_bonus
    confidence = round(min(1.0, raw_conf), 3)
    is_match = bool(confidence >= threshold)


    return {
        'confidence': confidence,
        'is_match': is_match,
        'signals': {
            'appearance': round(s_app, 3),
            'spatial': round(s_spatial, 3),
            'temporal': round(s_temp, 3),
            'zone': round(s_zone, 3),
            'distance': round(avg_dist, 1),
            'is_simultaneous': is_simultaneous,
        },
    }


class GlobalPerson:
    """Unified store-level person identity spanning multiple camera feeds."""

    def __init__(self, global_id: int):
        self.global_id = global_id
        self.global_label = f'GLOBAL {global_id:03d}'
        self.global_code = f'G{global_id:02d}'
        self.camera_tracks: dict[str, int] = {}  # camera_id -> local_track_id
        self.first_seen: float = 999999.0
        self.last_seen: float = 0.0
        self.match_confidence: float = 1.0
        self.is_merged: bool = False
        self.appearance_feature: list[float] = []
        self.trajectory: list[dict] = []  # [{t, cam, x, y, zone, zone_name}]

    def add_camera_track(
        self,
        camera_id: str,
        track_id: int,
        first_seen: float,
        last_seen: float,
        feat: list[float],
        trajectory: list[dict],
        confidence: float = 1.0,
    ):
        self.camera_tracks[camera_id] = track_id
        self.first_seen = min(self.first_seen, first_seen)
        self.last_seen = max(self.last_seen, last_seen)
        if len(self.camera_tracks) > 1:
            self.is_merged = True
            self.match_confidence = round(confidence, 3)
        if feat and not self.appearance_feature:
            self.appearance_feature = feat
        elif feat and self.appearance_feature and np is not None:
            # Running average feature
            comb = (np.array(self.appearance_feature) + np.array(feat)) / 2.0
            norm = float(np.linalg.norm(comb))
            if norm > 1e-6:
                self.appearance_feature = [round(float(v), 4) for v in (comb / norm)]
        self.trajectory.extend(trajectory)
        self.trajectory.sort(key=lambda pt: pt['t'])

    @property
    def dwell_seconds(self) -> float:
        return max(0.0, round(self.last_seen - self.first_seen, 1))

    def to_dict(self) -> dict:
        cams_tag = ', '.join(f"{'C1' if c == 'camera_01' else 'C2'}-{tid}" for c, tid in self.camera_tracks.items())
        return {
            'global_id': self.global_id,
            'global_label': self.global_label,
            'global_code': self.global_code,
            'display_label': f'{self.global_label} ({cams_tag})' if self.is_merged else f'{self.global_label} ({cams_tag})',
            'camera_tracks': self.camera_tracks,
            'is_merged': self.is_merged,
            'match_confidence': self.match_confidence,
            'first_seen': round(self.first_seen, 2),
            'last_seen': round(self.last_seen, 2),
            'dwell_seconds': self.dwell_seconds,
            'zones_visited': list(dict.fromkeys(pt['zone_name'] for pt in self.trajectory if pt.get('zone_name'))),
        }


class GlobalIdentityManager:
    """Manages cross-camera association, Global Person lifecycle, and deduplicated metrics."""

    def __init__(self, threshold: float = DEFAULT_REID_THRESHOLD):
        self.threshold = threshold
        self._cached_hash: str = ''
        self._global_people: list[GlobalPerson] = []
        self._camera_to_global: dict[tuple[str, int], int] = {}  # (cam_id, track_id) -> global_id
        self._track_features_cache: dict[str, dict] = {}  # cam_id -> {track_id: feature}

    def _ensure_track_features(self, job, camera_id: str):
        """Compute and cache average appearance features per track from video."""
        if job is None or job.state != 'ready' or not getattr(job, 'frames', []):
            return {}

        cache = self._track_features_cache.get(camera_id)
        if cache is not None:
            return cache

        # Check if features are already attached inside job.frames
        has_embedded_feats = any(
            any('feature' in p for p in f.get('people', []))
            for f in job.frames[:5]
        )

        features_by_track = defaultdict(list)
        positions_by_track = defaultdict(dict)
        zones_by_track = defaultdict(set)
        trajectories_by_track = defaultdict(list)

        if has_embedded_feats:
            for f in job.frames:
                t = f['t']
                for p in f.get('people', []):
                    pid = p['id']
                    if 'feature' in p and p['feature']:
                        features_by_track[pid].append(p['feature'])
                    t_round = round(t, 1)
                    pos = (p['map']['x'], p['map']['y'])
                    positions_by_track[pid][t_round] = pos
                    zones_by_track[pid].add(p['zone'])
                    trajectories_by_track[pid].append({
                        't': t,
                        'cam': camera_id,
                        'x': pos[0],
                        'y': pos[1],
                        'zone': p['zone'],
                        'zone_name': p.get('zone_name', p['zone']),
                    })
        else:
            # Extract features from video file for each track bounding box
            video_path = getattr(job, 'video_path', None)
            if cv2 is not None and video_path and os.path.isfile(video_path):
                cap = cv2.VideoCapture(video_path)
                frame_idx = 0
                sample_step = getattr(job, 'sample_every', 5) or 5
                frame_cursor = 0

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_idx += 1
                    if (frame_idx - 1) % sample_step != 0:
                        continue
                    if frame_cursor >= len(job.frames):
                        break

                    job_frame = job.frames[frame_cursor]
                    t = job_frame['t']
                    frame_cursor += 1

                    for p in job_frame.get('people', []):
                        pid = p['id']
                        bbox = p.get('bbox')
                        if bbox:
                            feat = extract_appearance_feature(frame, bbox)
                            # Attach to frame object for fast subsequent calls
                            p['feature'] = feat
                            features_by_track[pid].append(feat)

                        t_round = round(t, 1)
                        pos = (p['map']['x'], p['map']['y'])
                        positions_by_track[pid][t_round] = pos
                        zones_by_track[pid].add(p['zone'])
                        trajectories_by_track[pid].append({
                            't': t,
                            'cam': camera_id,
                            'x': pos[0],
                            'y': pos[1],
                            'zone': p['zone'],
                            'zone_name': p.get('zone_name', p['zone']),
                        })
                cap.release()

        # Build track summaries
        track_summaries = {}
        for pid, lc in job.lifecycles.items():
            feats = features_by_track.get(pid, [])
            if feats and np is not None:
                mean_f = np.mean(feats, axis=0)
                norm = float(np.linalg.norm(mean_f))
                final_feat = [round(float(v), 4) for v in (mean_f / norm)] if norm > 1e-6 else feats[0]
            elif feats:
                final_feat = feats[0]
            else:
                final_feat = [0.0] * 32

            pts = list(positions_by_track.get(pid, {}).values())
            mean_pos = (
                sum(pt[0] for pt in pts) / max(len(pts), 1),
                sum(pt[1] for pt in pts) / max(len(pts), 1),
            ) if pts else (50.0, 50.0)

            track_summaries[pid] = {
                'id': pid,
                'camera_id': camera_id,
                'first_seen': lc.get('first_seen', 0.0),
                'last_seen': lc.get('last_seen', 0.0),
                'feature': final_feat,
                'positions_by_t': positions_by_track.get(pid, {}),
                'mean_pos': mean_pos,
                'first_pos': pts[0] if pts else mean_pos,
                'last_pos': pts[-1] if pts else mean_pos,
                'zones': list(zones_by_track.get(pid, [])),
                'trajectory': trajectories_by_track.get(pid, []),
            }

        self._track_features_cache[camera_id] = track_summaries
        return track_summaries

    def synchronize(self, job1, job2, camera_1_id: str = 'camera_01', camera_2_id: str = 'camera_02'):
        """Build global identity associations across Camera 01 and Camera 02."""
        h1 = f'{camera_1_id}:{getattr(job1, "state", "")}:{len(getattr(job1, "frames", []))}'
        h2 = f'{camera_2_id}:{getattr(job2, "state", "")}:{len(getattr(job2, "frames", []))}'
        cache_key = f'{h1}|{h2}|{self.threshold}'
        if self._cached_hash == cache_key and self._global_people:
            return

        tracks1 = self._ensure_track_features(job1, camera_1_id)
        tracks2 = self._ensure_track_features(job2, camera_2_id)

        # Filter candidate tracks: require at least 1.0s track duration for cross-camera matching
        valid_tracks1 = {id1: t1 for id1, t1 in tracks1.items() if (t1.get('last_seen', 0.0) - t1.get('first_seen', 0.0)) >= 1.0}
        valid_tracks2 = {id2: t2 for id2, t2 in tracks2.items() if (t2.get('last_seen', 0.0) - t2.get('first_seen', 0.0)) >= 1.0}

        # Compute candidate match matrix
        candidates = []
        for id1, t1 in valid_tracks1.items():
            for id2, t2 in valid_tracks2.items():
                res = compute_cross_camera_match(t1, t2, threshold=self.threshold)
                if res['is_match']:
                    candidates.append({
                        'conf': res['confidence'],
                        'id1': id1,
                        'id2': id2,
                        'signals': res['signals'],
                    })

        pairs = []
        try:
            from scipy.optimize import linear_sum_assignment
            v1_ids = list(valid_tracks1.keys())
            v2_ids = list(valid_tracks2.keys())
            if v1_ids and v2_ids and np is not None:
                cand_map = {(c['id1'], c['id2']): c for c in candidates}
                cost = np.full((len(v1_ids), len(v2_ids)), 10.0)
                for i, id1 in enumerate(v1_ids):
                    for j, id2 in enumerate(v2_ids):
                        if (id1, id2) in cand_map:
                            cost[i, j] = 1.0 - cand_map[(id1, id2)]['conf']
                row_ind, col_ind = linear_sum_assignment(cost)
                for r, c in zip(row_ind, col_ind):
                    if cost[r, c] < 5.0:
                        cand = cand_map.get((v1_ids[r], v2_ids[c]))
                        if cand:
                            pairs.append(cand)
        except Exception:
            pairs = []

        if not pairs:
            # Greedy maximum-confidence bipartite matching fallback
            candidates.sort(
                key=lambda c: (
                    c['signals'].get('is_simultaneous', False),
                    c['signals'].get('temporal', 0.0) >= 0.70,
                    c['conf'],
                ),
                reverse=True,
            )
            matched_1 = set()
            matched_2 = set()
            for cand in candidates:
                if cand['id1'] not in matched_1 and cand['id2'] not in matched_2:
                    matched_1.add(cand['id1'])
                    matched_2.add(cand['id2'])
                    pairs.append(cand)

        matched_1 = {p['id1'] for p in pairs}
        matched_2 = {p['id2'] for p in pairs}
        for p in pairs:
            log.info(
                '[CROSS-CAMERA RE-ID] Matched C1-%s <-> C2-%s (Confidence: %.2f, Signals: %s)',
                p['id1'], p['id2'], p['conf'], p['signals'],
            )

        # Construct GlobalPerson instances
        global_people = []
        cam_to_global = {}
        gid_seq = 1

        # 1. Add matched cross-camera people
        for p in pairs:
            gp = GlobalPerson(global_id=gid_seq)
            t1 = tracks1[p['id1']]
            t2 = tracks2[p['id2']]
            gp.add_camera_track(
                camera_1_id, p['id1'], t1['first_seen'], t1['last_seen'],
                t1['feature'], t1['trajectory'], confidence=p['conf'],
            )
            gp.add_camera_track(
                camera_2_id, p['id2'], t2['first_seen'], t2['last_seen'],
                t2['feature'], t2['trajectory'], confidence=p['conf'],
            )
            global_people.append(gp)
            cam_to_global[(camera_1_id, p['id1'])] = gid_seq
            cam_to_global[(camera_2_id, p['id2'])] = gid_seq
            gid_seq += 1

        # 2. Add remaining unmatched Camera 01 tracks
        for id1, t1 in tracks1.items():
            if id1 not in matched_1:
                gp = GlobalPerson(global_id=gid_seq)
                gp.add_camera_track(
                    camera_1_id, id1, t1['first_seen'], t1['last_seen'],
                    t1['feature'], t1['trajectory'], confidence=1.0,
                )
                global_people.append(gp)
                cam_to_global[(camera_1_id, id1)] = gid_seq
                gid_seq += 1

        # 3. Add remaining unmatched Camera 02 tracks
        for id2, t2 in tracks2.items():
            if id2 not in matched_2:
                gp = GlobalPerson(global_id=gid_seq)
                gp.add_camera_track(
                    camera_2_id, id2, t2['first_seen'], t2['last_seen'],
                    t2['feature'], t2['trajectory'], confidence=1.0,
                )
                global_people.append(gp)
                cam_to_global[(camera_2_id, id2)] = gid_seq
                gid_seq += 1

        self._global_people = global_people
        self._camera_to_global = cam_to_global
        self._cached_hash = cache_key

    def get_global_id_for_track(self, camera_id: str, track_id: int) -> int | None:
        return self._camera_to_global.get((camera_id, track_id))

    def get_global_person(self, global_id: int) -> GlobalPerson | None:
        for gp in self._global_people:
            if gp.global_id == global_id:
                return gp
        return None

    def get_active_global_people(
        self,
        job1,
        job2,
        t1: float = 0.0,
        t2: float = 0.0,
        camera_1_id: str = 'camera_01',
        camera_2_id: str = 'camera_02',
    ) -> list[dict]:
        """Return active Global Persons deduplicated at current playback timestamps."""
        self.synchronize(job1, job2, camera_1_id, camera_2_id)

        raw_c1 = {p['id']: p for p in (job1.tracks_at(t1) if job1 and job1.state == 'ready' else [])}
        raw_c2 = {p['id']: p for p in (job2.tracks_at(t2) if job2 and job2.state == 'ready' else [])}

        active_list = []
        for gp in self._global_people:
            c1_tid = gp.camera_tracks.get(camera_1_id)
            c2_tid = gp.camera_tracks.get(camera_2_id)

            p1 = raw_c1.get(c1_tid) if c1_tid is not None else None
            p2 = raw_c2.get(c2_tid) if c2_tid is not None else None

            if p1 is None and p2 is None:
                continue

            # Determine active presence
            active_cams = []
            if p1 is not None:
                active_cams.append(camera_1_id)
            if p2 is not None:
                active_cams.append(camera_2_id)

            # Choose best representative telemetry (prefer primary or higher confidence)
            rep_p = p1 if p1 is not None else p2

            # If seen simultaneously in both cameras, smooth or select best
            if p1 is not None and p2 is not None:
                rep_cam = camera_1_id if p1.get('confidence', 0) >= p2.get('confidence', 0) else camera_2_id
                map_x = round((p1['map']['x'] + p2['map']['x']) / 2.0, 1)
                map_y = round((p1['map']['y'] + p2['map']['y']) / 2.0, 1)
                dwell = max(p1.get('dwell', 0.0), p2.get('dwell', 0.0))
                conf = max(p1.get('confidence', 0.0), p2.get('confidence', 0.0))
            else:
                rep_cam = active_cams[0]
                map_x = rep_p['map']['x']
                map_y = rep_p['map']['y']
                dwell = rep_p.get('dwell', 0.0)
                conf = rep_p.get('confidence', 0.0)

            cams_label = 'BOTH CAMERAS' if len(active_cams) == 2 else ('CAMERA 01' if active_cams[0] == camera_1_id else 'CAMERA 02')
            cams_tag = ', '.join(f"{'C1' if c == 'camera_01' else 'C2'}-{tid}" for c, tid in gp.camera_tracks.items())
            active_list.append({
                'global_id': gp.global_id,
                'global_label': gp.global_label,
                'global_code': gp.global_code,
                'display_label': f'{gp.global_label} ({cams_tag})',
                'is_merged': gp.is_merged,
                'match_confidence': gp.match_confidence,
                'active_cameras': active_cams,
                'active_cameras_label': cams_label,
                'camera_tracks': gp.camera_tracks,
                'primary_cam': rep_cam,
                'primary_track_id': rep_p['id'],
                'x': map_x,
                'y': map_y,
                'map': {'x': map_x, 'y': map_y},
                'zone': rep_p.get('zone', 'aisle'),
                'zone_name': rep_p.get('zone_name', 'Aisle'),
                'dwell': dwell,
                'confidence': conf,
                'first_seen': gp.first_seen,
                'last_seen': gp.last_seen,
            })

        active_list.sort(key=lambda item: item['global_id'])
        return active_list

    def get_store_metrics(
        self,
        job1,
        job2,
        t1: float = 0.0,
        t2: float = 0.0,
        camera_1_id: str = 'camera_01',
        camera_2_id: str = 'camera_02',
    ) -> dict:
        """Deduplicated store metrics derived from Global Person IDs."""
        self.synchronize(job1, job2, camera_1_id, camera_2_id)
        active_people = self.get_active_global_people(job1, job2, t1, t2, camera_1_id, camera_2_id)

        # Raw camera observations
        raw_c1 = len(job1.tracks_at(t1)) if job1 and job1.state == 'ready' else 0
        raw_c2 = len(job2.tracks_at(t2)) if job2 and job2.state == 'ready' else 0
        raw_total = raw_c1 + raw_c2

        # Deduplicated store occupancy
        store_occupancy = len(active_people)

        # Cross-camera matches currently active
        active_matches = sum(1 for p in active_people if len(p['active_cameras']) > 1)
        total_matched_people = sum(1 for gp in self._global_people if gp.is_merged)

        # Historical entries and exits using unified global lifecycles
        t_max = max(t1, t2)
        entered_people = [gp for gp in self._global_people if gp.first_seen <= t_max]
        total_unique_visitors = len(entered_people)

        exited_people = [gp for gp in entered_people if gp.last_seen < t_max - 5.0]
        total_exits = len(exited_people)

        dwells = [gp.last_seen - gp.first_seen for gp in entered_people if gp.last_seen > gp.first_seen]
        avg_dwell_secs = round(sum(dwells) / len(dwells), 1) if dwells else 0.0

        merged_confs = [gp.match_confidence for gp in self._global_people if gp.is_merged]
        avg_match_conf = round(sum(merged_confs) / len(merged_confs), 2) if merged_confs else 0.0

        return {
            'store_occupancy': store_occupancy,
            'raw_camera_tracks': raw_total,
            'active_matches': active_matches,
            'total_matched_people': total_matched_people,
            'total_unique_visitors': total_unique_visitors,
            'total_entries': total_unique_visitors,
            'total_exits': total_exits,
            'avg_dwell_secs': avg_dwell_secs,
            'avg_match_confidence': avg_match_conf,
            'threshold': self.threshold,
            'active_people': active_people,
        }


# Global singleton instance
global_identity_manager = GlobalIdentityManager()
