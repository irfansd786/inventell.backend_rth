from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.inventory import Inventory
from app.schemas.inventory import InventoryOut, ReplenishIn
from app.services import inventory_service as svc

router = APIRouter(prefix='/inventory', tags=['inventory'])


def _to_out(inv: Inventory) -> dict:
    return {
        'id': inv.id,
        'product_id': inv.product_id,
        'name': inv.product.name if inv.product else '',
        'sku': inv.product.sku if inv.product else '',
        'price': inv.product.price if inv.product else 0,
        'store_stock': inv.store_stock or 0,
        'warehouse_stock': inv.warehouse_stock or 0,
        'reserved_stock': inv.reserved_stock or 0,
        'reorder_level': inv.reorder_level or 0,
        'status': inv.status,
        'available_stock': inv.available_stock,
    }


@router.get('')
def list_inventory(
    status: str | None = None,
    category: str | None = None,
    risk_type: str | None = None,
    demand_level: str | None = None,
    period_days: int | None = 30,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return svc.get_enriched_inventory(
        db,
        status=status,
        category=category,
        risk_type=risk_type,
        demand_level=demand_level,
        period_days=period_days,
        search=search,
    )


@router.get('/summary')
def summary(
    period_days: int | None = 30,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return svc.get_inventory_summary(db, period_days=period_days)


@router.get('/low-stock')
def low_stock(
    category: str | None = None,
    severity: str | None = None,
    risk_type: str | None = None,
    demand_risk: str | None = None,
    demand_level: str | None = None,
    period_days: int | None = 30,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return svc.get_low_stock_matrix(
        db,
        category=category,
        severity=severity,
        risk_type=risk_type,
        demand_risk=demand_risk,
        demand_level=demand_level,
        period_days=period_days,
        search=search,
    )


@router.get('/critical')
def critical(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_low_stock_matrix(db, severity='Critical')


@router.get('/{product_id}')
def by_product(product_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if inv is None:
        raise HTTPException(status_code=404, detail='Inventory record not found')
    items = svc.get_enriched_inventory(db)
    for it in items:
        if it['product_id'] == product_id:
            return it
    return _to_out(inv)


@router.post('/replenish')
def replenish(payload: ReplenishIn, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    inv = svc.replenish(db, payload.product_id, payload.quantity)
    items = svc.get_enriched_inventory(db)
    for it in items:
        if it['product_id'] == payload.product_id:
            return it
    return _to_out(inv)
