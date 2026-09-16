from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.alert import Alert
from app.services import risk_service as svc

router = APIRouter(prefix='/alerts', tags=['alerts'])


@router.get('')
def list_alerts(limit: int = 20, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.list_alerts(db, min(limit, 100))


@router.post('/{alert_id}/read')
def mark_read(alert_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        return {'status': 'not found'}
    alert.is_read = True
    db.commit()
    return {'status': 'read'}
