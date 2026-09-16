from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.risk import Risk
from app.schemas.ops import RiskCreate, RiskOut
from app.services import risk_service as svc

router = APIRouter(prefix='/risks', tags=['risks'])


@router.get('')
def list_risks(
    status: str | None = None,
    severity: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return svc.list_risks(db, status=status, severity=severity)


@router.get('/summary')
def summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.risk_summary(db)


@router.get('/{risk_id}', response_model=RiskOut)
def get_risk(risk_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if risk is None:
        raise HTTPException(status_code=404, detail='Risk not found')
    return risk


@router.post('', response_model=RiskOut, status_code=201)
def create_risk(payload: RiskCreate, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    risk = Risk(**payload.model_dump())
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


@router.post('/{risk_id}/resolve', response_model=RiskOut)
def resolve_risk(risk_id: int, note: dict | None = None, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if risk is None:
        raise HTTPException(status_code=404, detail='Risk not found')
    return svc.resolve_risk(db, risk, (note or {}).get('note', ''))
