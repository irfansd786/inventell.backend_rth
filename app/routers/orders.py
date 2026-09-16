from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.order import Order
from app.schemas.order import OrderIn, OrderOut, OrderStatusIn
from app.services.order_service import ACTION_TO_STATUS, create_order, transition_order

router = APIRouter(prefix='/orders', tags=['orders'])


@router.get('')
def list_orders(
    q: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    query = db.query(Order).order_by(Order.created_at.desc())
    if status:
        query = query.filter(Order.status == status.upper())
    if q:
        query = query.filter(Order.order_number.ilike(f'%{q}%'))
    return query.limit(min(limit, 200)).all()


@router.get('/{order_id}', response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return order


@router.post('', response_model=OrderOut, status_code=201)
def create(payload: OrderIn, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return create_order(db, payload.customer_id, payload.items)


@router.post('/{order_id}/{action}', response_model=OrderOut)
def transition(order_id: int, action: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    target = ACTION_TO_STATUS.get(action)
    if target is None:
        raise HTTPException(status_code=422, detail=f'Unknown action: {action}')
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return transition_order(db, order, target)


@router.put('/{order_id}/status', response_model=OrderOut)
def set_status(order_id: int, payload: OrderStatusIn, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return transition_order(db, order, payload.status.upper())
