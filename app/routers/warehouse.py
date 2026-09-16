from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.inventory import Inventory
from app.models.transfer import Transfer
from app.models.warehouse import Warehouse
from app.schemas.ops import WarehouseOut

router = APIRouter(prefix='/warehouse', tags=['warehouse'])


@router.get('', response_model=list[WarehouseOut])
def list_warehouses(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return db.query(Warehouse).all()


@router.get('/overview')
def overview(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    warehouse = db.query(Warehouse).first()
    units = db.query(func.coalesce(func.sum(Inventory.warehouse_stock), 0)).first()[0]
    pending = db.query(Transfer).filter(Transfer.status == 'PENDING').count()
    return {
        'warehouse': warehouse.name if warehouse else 'Main Warehouse',
        'units': int(units or 0),
        'pending_transfers': pending,
    }
