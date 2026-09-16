from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services import recommendation_service as svc

router = APIRouter(prefix='/recommendations', tags=['recommendations'])


@router.get('')
@router.get('/')
def list_recommendations(
    status: str | None = None,
    recommendation_type: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Returns all persistent inventory recommendations with real state."""
    return svc.list_recommendations(db, status=status, recommendation_type=recommendation_type)


@router.post('/{rec_id}/approve')
def approve_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Approve a pending recommendation (PENDING -> APPROVED)."""
    return svc.approve_recommendation(db, rec_id)


@router.post('/{rec_id}/launch')
def launch_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Launch an approved recommendation (APPROVED -> LAUNCHED), triggering real transfer/promotion workflow."""
    return svc.launch_recommendation(db, rec_id)


@router.post('/{rec_id}/reject')
def reject_recommendation(
    rec_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Reject a recommendation (PENDING/APPROVED -> REJECTED)."""
    return svc.reject_recommendation(db, rec_id)
