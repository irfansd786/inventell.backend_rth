from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.services import finance_service as svc

router = APIRouter(prefix='/finance', tags=['finance'])


@router.get('/summary')
def summary(db: Session = Depends(get_db), _user=Depends(require_permission('finance'))):
    """P&L aggregates computed from ingested sales (historical dataset)."""
    return svc.get_summary(db)
