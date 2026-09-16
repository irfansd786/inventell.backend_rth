from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.transfer import Transfer
from app.models.warehouse import Warehouse
from app.schemas.ops import TransferIn, TransferOut
from app.services import inventory_service as inv_svc

router = APIRouter(prefix='/transfers', tags=['transfers'])


@router.get('')
def list_transfers(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    rows = db.query(Transfer).order_by(Transfer.created_at.desc()).limit(100).all()
    return [
        {
            'id': t.id,
            'transfer_number': t.transfer_number,
            'warehouse_id': t.warehouse_id,
            'warehouse_name': t.warehouse.name if t.warehouse else '',
            'product_id': t.product_id,
            'product_name': t.product.name if t.product else '',
            'product_sku': t.product.sku if t.product else '',
            'quantity': t.quantity,
            'status': t.status,
            'created_at': t.created_at.isoformat() if t.created_at else '',
        }
        for t in rows
    ]


@router.post('', response_model=TransferOut, status_code=201)
def create_transfer(payload: TransferIn, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return _execute(db, payload)


@router.post('/{transfer_id}/approve', response_model=TransferOut)
def approve_transfer(transfer_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    transfer = db.query(Transfer).filter(Transfer.id == transfer_id).first()
    if transfer is None:
        raise HTTPException(status_code=404, detail='Transfer not found')
    if transfer.status != 'PENDING':
        raise HTTPException(status_code=422, detail='Only PENDING transfers can be approved')
    inv = inv_svc.replenish(db, transfer.product_id, transfer.quantity)
    transfer.status = 'COMPLETED'
    db.commit()
    db.refresh(transfer)
    return transfer


def _execute(db: Session, payload: TransferIn) -> Transfer:
    warehouse = (
        db.query(Warehouse).filter(Warehouse.id == payload.warehouse_id).first()
        if payload.warehouse_id
        else db.query(Warehouse).first()
    )
    if warehouse is None:
        raise HTTPException(status_code=404, detail='Warehouse not found')
    count = db.query(Transfer).count() + 1
    transfer = Transfer(
        transfer_number=f'TRF-{count:05d}',
        warehouse_id=warehouse.id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        status='COMPLETED',
    )
    db.add(transfer)
    db.flush()
    inv_svc.replenish(db, payload.product_id, payload.quantity)
    db.refresh(transfer)
    return transfer
