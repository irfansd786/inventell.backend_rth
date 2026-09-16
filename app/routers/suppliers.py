from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.supplier import Supplier
from app.schemas.ops import SupplierIn, SupplierOut

router = APIRouter(prefix='/suppliers', tags=['suppliers'])


@router.get('', response_model=list[SupplierOut])
def list_suppliers(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(Supplier).order_by(Supplier.name).all()


@router.post('', response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get('/{supplier_id}', response_model=SupplierOut)
def get_supplier(supplier_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail='Supplier not found')
    return supplier
