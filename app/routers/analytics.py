import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.alert import Alert
from app.models.queue_alert import QueueAlert
from app.routers.store_monitor import _get_job
from app.services import analytics_service as svc
from app.services import dashboard_service as dash_svc
from app.services import queue_intelligence_service as queue_svc
from app.services import store_intelligence_service as cv_svc

router = APIRouter(prefix='/analytics', tags=['analytics'])


class QueueSettingsIn(BaseModel):
    threshold_normal_max: int | None = None
    threshold_moderate_max: int | None = None
    threshold_high_max: int | None = None
    alert_threshold: int | None = None
    critical_threshold: int | None = None
    long_wait_seconds: float | None = None


class QueueActionIn(BaseModel):
    action: str
    notes: str | None = ''


@router.get('/kpis')
@router.get('/dashboard')
def dashboard_analytics(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return dash_svc.get_summary(db)


@router.get('/customers/combined')
def combined_customer_analytics(
    timestamp: float = 0.0,
    period: str = Query(default='today'),
    granularity: str = Query(default='hourly'),
    window_start: float | None = Query(default=None, ge=0),
    window_end: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Store-level customer analytics across camera_01 + camera_02.

    Both tracking jobs are merged (track IDs namespaced per camera — no
    cross-camera identity matching) and aggregated by the same pipeline.
    A failing camera never blocks the other; per-camera status is reported.
    """
    return cv_svc.get_combined_customer_analytics(
        _get_job('camera_01'),
        _get_job('camera_02'),
        t=timestamp,
        granularity=granularity,
        period=period,
        window_start=window_start,
        window_end=window_end,
        db=db,
    )


@router.get('/customers')
@router.get('/customers/today')
def customer_analytics(
    camera_id: str = 'camera_01',
    timestamp: float = 0.0,
    period: str = Query(default='today'),
    granularity: str = Query(default='hourly'),
    window_start: float | None = Query(default=None, ge=0),
    window_end: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Customer behavior analytics from the shared CCTV tracking pipeline.

    One stable ByteTrack ID == one anonymous customer session. All metrics
    derive from job.frames / job.lifecycles; no fake floors or placeholders.
    """
    job = _get_job(camera_id)
    return cv_svc.get_customer_analytics(
        job,
        t=timestamp,
        granularity=granularity,
        period=period,
        window_start=window_start,
        window_end=window_end,
        db=db,
        camera_id=camera_id,
    )


@router.get('/zones/combined')
def combined_zone_analytics(
    timestamp: float = 0.0,
    period: str = Query(default='today'),
    camera_id: str = Query(default='combined'),
    window_start: float | None = Query(default=None, ge=0),
    window_end: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Store-level zone intelligence across Camera 01 + Camera 02."""
    return cv_svc.get_combined_zones_analytics(
        _get_job('camera_01'),
        _get_job('camera_02'),
        t=timestamp,
        period=period,
        window_start=window_start,
        window_end=window_end,
        db=db,
        camera_id=camera_id,
    )


@router.get('/zones')
def zone_analytics(
    camera_id: str = 'combined',
    timestamp: float = 0.0,
    period: str = Query(default='today'),
    window_start: float | None = Query(default=None, ge=0),
    window_end: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    if camera_id == 'combined':
        return cv_svc.get_combined_zones_analytics(
            _get_job('camera_01'),
            _get_job('camera_02'),
            t=timestamp,
            period=period,
            window_start=window_start,
            window_end=window_end,
            db=db,
            camera_id=camera_id,
        )
    job = _get_job(camera_id)
    return {'items': cv_svc.get_zones(job, timestamp)}


@router.get('/heatmap/combined')
def combined_heatmap_analytics(
    timestamp: float = 0.0,
    metric: str = Query(default='traffic'),
    period: str = Query(default='today'),
    range: str | None = Query(default=None),
    camera_id: str = Query(default='combined'),
    window_start: float | None = Query(default=None, ge=0),
    window_end: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Store-level heatmap spatial intelligence across Camera 01 + Camera 02."""
    effective_period = range.lower() if range else period
    return cv_svc.get_combined_heatmap_analytics(
        _get_job('camera_01'),
        _get_job('camera_02'),
        t=timestamp,
        metric=metric,
        period=effective_period,
        window_start=window_start,
        window_end=window_end,
        db=db,
        camera_id=camera_id,
    )


@router.get('/heatmap')
def heatmap_analytics(
    camera_id: str = 'combined',
    timestamp: float = 0.0,
    metric: str = Query('Customer Density'),
    range: str = Query('Today'),
    period: str = Query(default='today'),
    window_start: float | None = Query(default=None, ge=0),
    window_end: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    if camera_id == 'combined':
        return cv_svc.get_combined_heatmap_analytics(
            _get_job('camera_01'),
            _get_job('camera_02'),
            t=timestamp,
            metric=metric,
            period=range.lower() if range else period,
            window_start=window_start,
            window_end=window_end,
            db=db,
        )
    job = _get_job(camera_id)
    return cv_svc.get_heatmap_points(job, timestamp, metric=metric, range_filter=range, db=db)


@router.get('/queue/settings')
def get_queue_settings(_user=Depends(get_current_user)):
    return queue_svc.load_queue_settings()


@router.post('/queue/settings')
@router.put('/queue/settings')
def update_queue_settings(payload: QueueSettingsIn, _user=Depends(get_current_user)):
    data = payload.model_dump(exclude_unset=True)
    return queue_svc.save_queue_settings(data)


@router.get('/queue')
@router.get('/queue-intelligence')
def queue_analytics(
    camera_id: str = 'camera_01',
    timestamp: float = 0.0,
    threshold: int | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    job1 = _get_job('camera_01')
    job2 = _get_job('camera_02')
    return queue_svc.get_queue_analytics_payload(
        job1=job1,
        job2=job2,
        camera_id=camera_id,
        t=timestamp,
        db=db,
        threshold_override=threshold,
    )


@router.get('/queue/alerts')
def list_queue_alerts(
    camera_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    q = db.query(QueueAlert).order_by(QueueAlert.created_at.desc())
    if camera_id and camera_id not in ('all', 'combined', 'store_summary'):
        q = q.filter(QueueAlert.camera_id == camera_id)
    if status and status != 'ALL':
        q = q.filter(QueueAlert.status == status)
    if severity and severity != 'ALL':
        q = q.filter(QueueAlert.severity == severity)
    items = q.limit(limit).all()
    return [
        {
            'id': qa.id,
            'time': qa.created_at.strftime('%H:%M'),
            'date': qa.created_at.strftime('%Y-%m-%d'),
            'camera': 'Camera 01' if qa.camera_id == 'camera_01' else ('Camera 02' if qa.camera_id == 'camera_02' else 'Unified CCTV'),
            'camera_id': qa.camera_id,
            'queue_length': qa.queue_length,
            'threshold': qa.threshold,
            'duration': f'{qa.duration_minutes} min',
            'duration_minutes': qa.duration_minutes,
            'severity': qa.severity,
            'recommendation': qa.recommendation,
            'reason': qa.reason,
            'status': qa.status,
            'action_taken': qa.action_taken,
        }
        for qa in items
    ]


@router.post('/queue/alerts/{alert_id}/action')
def record_queue_alert_action(
    alert_id: int,
    payload: QueueActionIn,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    qa = db.query(QueueAlert).filter(QueueAlert.id == alert_id).first()
    if not qa:
        qa = db.query(QueueAlert).filter(QueueAlert.status == 'Active').order_by(QueueAlert.created_at.desc()).first()
    if not qa:
        return {'status': 'not_found', 'message': 'No queue alert to update'}
    action_label_map = {
        'open_counter': 'Open Additional Counter',
        'assign_staff': 'Assign Additional Staff',
        'dismiss': 'Dismiss Alert',
        'review_counter': 'Review Counter Diagnostics',
    }
    label = action_label_map.get(payload.action, payload.action)
    qa.action_taken = label
    qa.action_notes = payload.notes or f'Manager action recorded: {label}'
    if payload.action == 'dismiss':
        qa.status = 'Dismissed'
    else:
        qa.status = 'Action Dispatched'
    qa.resolved_at = datetime.datetime.now(datetime.timezone.utc)

    # Also mark navbar alert as read
    nb_alert = db.query(Alert).filter(Alert.category == 'queue', Alert.is_read == False).first()
    if nb_alert:
        nb_alert.is_read = True
    db.commit()
    return {
        'status': 'success',
        'alert_id': qa.id,
        'action_taken': label,
        'current_status': qa.status,
        'message': f'Queue action recorded: {label}',
    }


@router.get('/shelf')
@router.get('/shelf-intelligence')
def shelf_analytics(
    camera_id: str = 'camera_01',
    timestamp: float = 0.0,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    job = _get_job(camera_id)
    return cv_svc.get_shelf_intelligence(db, job, timestamp)


@router.get('/revenue-trend')
@router.get('/sales')
def sales_analytics(
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return {
        'data_provenance': 'Historical Dataset (M5 Forecasting)',
        'summary': svc.get_kpis(db),
        'trend': svc.get_revenue_trend(db, days=days),
        'categories': svc.get_category_performance(db),
    }


@router.get('/category-performance')
def category_performance(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_category_performance(db)


@router.get('/inventory')
def inventory_analytics(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return {
        'data_provenance': 'Retail Inventory Dataset & M5 Ingestion',
        'health': dash_svc.get_inventory_health(db),
        'turnover': svc.inventory_turnover(db),
    }


@router.get('/forecast')
def forecast_analytics(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    from app.routers import forecast as fc_router
    return fc_router.get_forecasts(db=db)


@router.get('/risks')
def risk_analytics(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return dash_svc.get_risks(db)


@router.get('/key-insights')
@router.get('/insights')
def key_insights(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return {'items': svc.get_key_insights(db)}

