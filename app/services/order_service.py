"""Order lifecycle enforcement: PENDING → ALLOCATED → PICKING → PACKING → READY → DISPATCHED."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.order import ALLOWED_TRANSITIONS, Order
from app.models.order_item import OrderItem
from app.models.product import Product

ACTION_TO_STATUS = {
    'allocate': 'ALLOCATED',
    'start-picking': 'PICKING',
    'start-packing': 'PACKING',
    'mark-ready': 'READY',
    'dispatch': 'DISPATCHED',
}


def transition_order(db: Session, order: Order, target: str) -> Order:
    allowed = ALLOWED_TRANSITIONS.get(order.status, tuple())
    if target not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f'Invalid transition: {order.status} → {target}',
        )
    # Reserve store stock when an order is allocated.
    if target == 'ALLOCATED':
        for item in order.items:
            inv = db.query(Inventory).filter(Inventory.product_id == item.product_id).first()
            if inv is None or inv.store_stock - inv.reserved_stock < item.quantity:
                raise HTTPException(status_code=409, detail='Insufficient store stock to allocate')
        for item in order.items:
            inv = db.query(Inventory).filter(Inventory.product_id == item.product_id).first()
            inv.reserved_stock = (inv.reserved_stock or 0) + item.quantity
    # Consume reserved stock when dispatched.
    if target == 'DISPATCHED':
        for item in order.items:
            inv = db.query(Inventory).filter(Inventory.product_id == item.product_id).first()
            if inv:
                inv.reserved_stock = max(0, (inv.reserved_stock or 0) - item.quantity)
                inv.store_stock = max(0, (inv.store_stock or 0) - item.quantity)
    order.status = target
    db.commit()
    db.refresh(order)
    return order


def create_order(db: Session, customer_id, items, prefix='ORD') -> Order:
    count = db.query(Order).count() + 1
    order = Order(
        order_number=f'{prefix}-{count:05d}',
        customer_id=customer_id,
        status='PENDING',
        total_amount=0.0,
    )
    db.add(order)
    db.flush()
    total = 0.0
    for entry in items:
        product = db.query(Product).filter(Product.id == entry.product_id).first()
        if product is None:
            raise HTTPException(status_code=404, detail=f'Product {entry.product_id} not found')
        price = entry.unit_price if entry.unit_price is not None else product.price
        total += price * entry.quantity
        db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=entry.quantity, unit_price=price))
    order.total_amount = total
    db.commit()
    db.refresh(order)
    return order
