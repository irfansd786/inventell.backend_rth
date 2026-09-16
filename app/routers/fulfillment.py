"""Fulfillment stage queues. Each stage only surfaces orders in its input state."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.order import Order

allocation_router = APIRouter(prefix='/allocation', tags=['fulfillment'])
picking_router = APIRouter(prefix='/picking', tags=['fulfillment'])
packing_router = APIRouter(prefix='/packing', tags=['fulfillment'])
dispatch_router = APIRouter(prefix='/dispatch', tags=['fulfillment'])


def _queue(db: Session, status: str, limit: int = 50):
    return (
        db.query(Order)
        .filter(Order.status == status)
        .order_by(Order.created_at.asc())
        .limit(limit)
        .all()
    )


@allocation_router.get('/queue')
def allocation_queue(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _queue(db, 'PENDING')


@picking_router.get('/queue')
def picking_queue(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _queue(db, 'ALLOCATED')


@packing_router.get('/queue')
def packing_queue(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _queue(db, 'PICKING')


@dispatch_router.get('/queue')
def dispatch_queue(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _queue(db, 'READY')
