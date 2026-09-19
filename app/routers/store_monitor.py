"""Store CCTV intelligence monitor API.

Pipeline: TEST VIDEO -> OpenCV -> person detection -> tracking -> foot
point -> homography -> 2D coordinates -> React (CCTV + 2D map).

Polling (REST) is used for testing videos; the service layer is shaped so a
 future /ws/store-monitor feed can replace polling without UI changes.
"""

import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.dependencies import get_current_user
from app.cv.calibration import get_calibration, save_calibration
from app.cv.reid import global_identity_manager
from app.cv.video_processor import ProcessingJob
from app.cv.video_source import UploadedVideoSource
from app.schemas.store_monitor import CalibrationIn, StartIn
from app.services import store_intelligence_service as svc

router = APIRouter(prefix='/store-monitor', tags=['store-monitor'])

MEDIA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'media', 'test_videos')
ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.webm'}

# camera_id -> ProcessingJob (one job per testing camera)
_jobs: dict[str, ProcessingJob] = {}


def _media_dir() -> str:
    os.makedirs(MEDIA_DIR, exist_ok=True)
    return MEDIA_DIR


def _video_path(camera_id: str) -> str | None:
    for ext in ('.mp4', '.avi', '.mov', '.webm'):
        candidate = os.path.join(_media_dir(), f'{camera_id}{ext}')
        if os.path.isfile(candidate):
            return candidate
    return None


def _tracks_path(camera_id: str) -> str | None:
    candidate = os.path.join(_media_dir(), f'{camera_id}.tracks.json')
    if os.path.isfile(candidate):
        return candidate
    return None


def _probe(path: str) -> dict:
    info = {'size_bytes': os.path.getsize(path)}
    try:
        source = UploadedVideoSource(path).open()
        info.update(source.metadata())
        source.release()
    except Exception:
        info['probe'] = 'unavailable'
    info.pop('path', None)
    return info


def _get_job(camera_id: str) -> ProcessingJob | None:
    job = _jobs.get(camera_id)
    if job is None:
        path = _video_path(camera_id) or os.path.join(_media_dir(), f'{camera_id}.mp4')
        if _video_path(camera_id) or _tracks_path(camera_id):
            job = ProcessingJob(camera_id, path)
            job.start()
            _jobs[camera_id] = job
    return _jobs.get(camera_id)


def _person_only(people: list) -> list:
    """Final API safety filter: only COCO PERSON tracks leave the backend."""
    out = []
    for p in people or []:
        if p.get('class_id', 0) != 0:
            continue
        name = p.get('class_name', 'person')
        if name is not None and str(name).lower() != 'person':
            continue
        out.append(p)
    return out


# ---------- testing videos (public: <video> tags cannot send JWT) ----------

@router.get('/videos')
def list_videos():
    out = []
    for camera_id in ('camera_01', 'camera_02'):
        path = _video_path(camera_id)
        if path:
            meta = _probe(path)
            meta.update({'camera_id': camera_id, 'filename': os.path.basename(path)})
            out.append(meta)
        elif _tracks_path(camera_id):
            out.append({
                'camera_id': camera_id,
                'filename': f'{camera_id}.mp4',
                'fps': 30,
                'width': 1920,
                'height': 1080,
                'duration': 60.0,
                'size_bytes': 0,
                'kind': 'test',
            })
    return {'items': out}


@router.get('/video/{camera_id}')
def stream_video(camera_id: str):
    path = _video_path(camera_id)
    if not path:
        raise HTTPException(status_code=404, detail=f'No testing video for {camera_id}')
    return FileResponse(path, media_type='video/mp4', filename=os.path.basename(path))


@router.post('/upload')
def upload_video(
    camera_id: str = 'camera_01',
    file: UploadFile = File(...),
    _user=Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f'Unsupported format. Use: {sorted(ALLOWED_EXTENSIONS)}')
    dest = os.path.join(_media_dir(), f'{camera_id}{ext}')
    with open(dest, 'wb') as fh:
        fh.write(file.file.read())
    _jobs.pop(camera_id, None)
    return {'camera_id': camera_id, 'filename': os.path.basename(dest), **_probe(dest)}


# ---------- processing control ----------

@router.post('/start')
def start_processing(payload: StartIn, _user=Depends(get_current_user)):
    path = _video_path(payload.camera_id) or os.path.join(_media_dir(), f'{payload.camera_id}.mp4')
    if not _video_path(payload.camera_id) and not _tracks_path(payload.camera_id):
        raise HTTPException(status_code=404, detail=f'No testing video or telemetry tracks for {payload.camera_id}')
    job = _jobs.get(payload.camera_id)
    if job is None or job.video_path != path:
        job = ProcessingJob(payload.camera_id, path)
        _jobs[payload.camera_id] = job
    return job.start(force=payload.force)


@router.post('/stop')
def stop_processing(payload: StartIn, _user=Depends(get_current_user)):
    job = _get_job(payload.camera_id)
    if job is None:
        return {'camera_id': payload.camera_id, 'state': 'idle'}
    return job.stop()


@router.get('/status')
def processing_status(camera_id: str = 'camera_01', _user=Depends(get_current_user)):
    job = _get_job(camera_id)
    has_feed = bool(_video_path(camera_id) or _tracks_path(camera_id))
    if job is None:
        return {'camera_id': camera_id, 'state': 'idle', 'progress': 0,
                'has_video': has_feed, 'engine': 'unknown', 'error': ''}
    return {**job.status(), 'has_video': has_feed}


# ---------- intelligence queries (timestamp-synchronized) ----------

@router.get('/cameras')
def cameras(_user=Depends(get_current_user)):
    """Dual-camera inventory: video source + processing state per camera.

    Both cameras are always reported; a failing camera never hides the other.
    """
    out = []
    for camera_id in ('camera_01', 'camera_02'):
        path = _video_path(camera_id)
        tracks = _tracks_path(camera_id)
        has_feed = bool(path or tracks)
        item = {'camera_id': camera_id, 'has_video': has_feed}
        if path:
            meta = _probe(path)
            meta.update({'filename': os.path.basename(path)})
            item['video'] = meta
        elif tracks:
            item['video'] = {
                'camera_id': camera_id,
                'filename': f'{camera_id}.mp4',
                'fps': 30,
                'width': 1920,
                'height': 1080,
                'duration': 60.0,
                'size_bytes': 0,
                'kind': 'test',
            }
        job = _get_job(camera_id)
        if job is None:
            item['status'] = {'camera_id': camera_id, 'state': 'idle', 'progress': 0,
                              'has_video': has_feed, 'engine': 'unknown', 'error': ''}
        else:
            item['status'] = {**job.status(), 'has_video': has_feed}
        out.append(item)
    return {'items': out}


@router.get('/summary')
def store_summary(t1: float = 0.0, t2: float = 0.0, _user=Depends(get_current_user)):
    """Store-level view across both cameras at their own analysis times.

    Per-camera jobs stay independent (no cross-camera ID merging); the
    combined block reports COMBINED CAMERA OBSERVATIONS with the limitation
    stated explicitly in the payload.
    """
    return svc.get_store_summary(_get_job('camera_01'), _get_job('camera_02'), t1, t2)


@router.get('/tracks')
def tracks(camera_id: str = 'camera_01', timestamp: float = 0.0, _user=Depends(get_current_user)):
    job = _get_job(camera_id)
    if job is None or job.state != 'ready':
        return {'camera_id': camera_id, 'timestamp': timestamp, 'connected': False, 'people': []}
    people = _person_only(job.tracks_at(timestamp))

    # Synchronize with global identity manager so local tracks carry Global IDs
    job1 = _get_job('camera_01')
    job2 = _get_job('camera_02')
    global_identity_manager.synchronize(job1, job2)

    # Check which tracks are active in the other camera at this timestamp
    other_cam_id = 'camera_02' if camera_id == 'camera_01' else 'camera_01'
    other_job = job2 if camera_id == 'camera_01' else job1
    other_active_pids = {
        p['id'] for p in _person_only(other_job.tracks_at(timestamp))
    } if other_job and other_job.state == 'ready' else set()

    annotated = []
    for p in people:
        p_row = dict(p)
        gid = global_identity_manager.get_global_id_for_track(camera_id, p['id'])
        if gid is not None:
            gp = global_identity_manager.get_global_person(gid)
            if gp:
                other_tid = gp.camera_tracks.get(other_cam_id)
                is_in_both_cams = bool(gp.is_merged and other_tid is not None and other_tid in other_active_pids)
                p_row['global_id'] = gp.global_id
                p_row['global_label'] = gp.global_label
                p_row['global_code'] = gp.global_code
                p_row['display_label'] = gp.to_dict()['display_label']
                p_row['is_merged'] = is_in_both_cams
                p_row['is_cross_matched'] = gp.is_merged
                p_row['match_confidence'] = gp.match_confidence
                p_row['camera_tracks'] = gp.camera_tracks
        annotated.append(p_row)
    return {'camera_id': camera_id, 'timestamp': timestamp, 'connected': True, 'people': annotated}


@router.get('/map')
def map_positions(camera_id: str = 'camera_01', timestamp: float = 0.0, _user=Depends(get_current_user)):
    job = _get_job(camera_id)
    people = _person_only(job.tracks_at(timestamp)) if job and job.state == 'ready' else []

    job1 = _get_job('camera_01')
    job2 = _get_job('camera_02')
    global_identity_manager.synchronize(job1, job2)

    other_cam_id = 'camera_02' if camera_id == 'camera_01' else 'camera_01'
    other_job = job2 if camera_id == 'camera_01' else job1
    other_active_pids = {
        p['id'] for p in _person_only(other_job.tracks_at(timestamp))
    } if other_job and other_job.state == 'ready' else set()

    out_people = []
    for p in people:
        gid = global_identity_manager.get_global_id_for_track(camera_id, p['id'])
        gp = global_identity_manager.get_global_person(gid) if gid else None
        item = {
            'id': p['id'],
            'class_id': 0,
            'class_name': 'person',
            'x': p['map']['x'],
            'y': p['map']['y'],
            'zone': p['zone'],
            'zone_name': p['zone_name'],
            'dwell': p['dwell'],
            'confidence': p['confidence'],
        }
        if gp:
            other_tid = gp.camera_tracks.get(other_cam_id)
            is_in_both_cams = bool(gp.is_merged and other_tid is not None and other_tid in other_active_pids)
            item.update({
                'global_id': gp.global_id,
                'global_label': gp.global_label,
                'global_code': gp.global_code,
                'display_label': gp.to_dict()['display_label'],
                'is_merged': is_in_both_cams,
                'is_cross_matched': gp.is_merged,
                'match_confidence': gp.match_confidence,
                'camera_tracks': gp.camera_tracks,
            })
        out_people.append(item)

    return {
        'camera_id': camera_id,
        'timestamp': timestamp,
        'connected': bool(job and job.state == 'ready'),
        'zones': svc.get_zones(job, timestamp),
        'people': out_people,
    }


@router.get('/global-people')
def global_people(t1: float = 0.0, t2: float = 0.0, _user=Depends(get_current_user)):
    """Return deduplicated active store-level people across both camera feeds."""
    j1 = _get_job('camera_01')
    j2 = _get_job('camera_02')
    return {
        'timestamp_c1': t1,
        'timestamp_c2': t2,
        'people': global_identity_manager.get_active_global_people(j1, j2, t1, t2),
        'metrics': global_identity_manager.get_store_metrics(j1, j2, t1, t2),
    }


@router.get('/global-journeys')
def global_journeys(t1: float = 0.0, t2: float = 0.0, _user=Depends(get_current_user)):
    """Unified chronological customer journeys merged across both cameras."""
    j1 = _get_job('camera_01')
    j2 = _get_job('camera_02')
    return {'items': svc.get_global_customer_journeys(j1, j2, t1, t2)}


@router.get('/metrics')
def metrics(camera_id: str = 'camera_01', timestamp: float = 0.0, _user=Depends(get_current_user)):
    return svc.get_metrics(_get_job(camera_id), timestamp)


@router.get('/session')
def session(camera_id: str = 'camera_01', timestamp: float = 0.0, _user=Depends(get_current_user)):
    """Customer session analytics from stable tracking IDs (Current Video Session).

    One stable ByteTrack ID == one customer. Never frame counts.
    """
    job = _get_job(camera_id)
    if job is None or job.state != 'ready':
        return {
            'camera_id': camera_id, 'connected': False, 'label': 'Current Video Session',
            'unique_customers': 0, 'entries': 0, 'exits': 0,
            'occupancy_now': 0, 'peak_occupancy': 0, 'avg_dwell_secs': 0,
        }
    lifecycles = getattr(job, 'lifecycles', {}) or {}
    seen = {int(k): v for k, v in lifecycles.items() if v.get('first_seen', 0) <= timestamp}
    current = _person_only(job.tracks_at(timestamp))
    peak = 0
    for frame in getattr(job, 'frames', []) or []:
        if frame.get('t', 0) > timestamp:
            break
        n = len(_person_only(frame.get('people', [])))
        if n > peak:
            peak = n
    dwells = [v.get('last_seen', 0) - v.get('first_seen', 0) for v in seen.values()]
    avg_dwell = round(sum(dwells) / len(dwells), 1) if dwells else 0
    exits = sum(1 for v in seen.values() if v.get('last_seen', 0) < timestamp - 5.0)
    return {
        'camera_id': camera_id, 'connected': True, 'label': 'Current Video Session',
        'unique_customers': len(seen),
        'entries': len(seen),
        'exits': exits,
        'occupancy_now': len(current),
        'peak_occupancy': peak,
        'avg_dwell_secs': avg_dwell,
    }


@router.get('/events')
def events(camera_id: str = 'camera_01', timestamp: float = 0.0, limit: int = 20,
           _user=Depends(get_current_user)):
    return {'items': svc.get_events(_get_job(camera_id), timestamp, limit)}


@router.get('/zones')
def zones(camera_id: str = 'camera_01', timestamp: float = 0.0, _user=Depends(get_current_user)):
    return {'items': svc.get_zones(_get_job(camera_id), timestamp)}


@router.get('/calibration')
def get_cal(camera_id: str = 'camera_01', _user=Depends(get_current_user)):
    return {'camera_id': camera_id, **get_calibration(camera_id)}


@router.put('/calibration')
def put_cal(camera_id: str = 'camera_01', payload: CalibrationIn = None,
            _user=Depends(get_current_user)):
    return {'camera_id': camera_id,
            **save_calibration(camera_id, payload.camera_points, payload.map_points)}
