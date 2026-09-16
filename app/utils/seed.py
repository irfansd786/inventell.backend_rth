"""Seed script — realistic, internally consistent demo data.

Rerunnable safely: every entity is looked up before insert, so running twice
creates nothing new.

Usage:
    python -m app.utils.seed
"""

import datetime
import json
import random

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models import *  # noqa: F401,F403 — register all models
from app.models.activity_log import ActivityLog
from app.models.alert import Alert
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.risk import Risk
from app.models.sale import Sale
from app.models.supplier import Supplier
from app.models.transfer import Transfer
from app.models.user import User
from app.models.warehouse import Warehouse
from app.services.inventory_service import classify_status

rng = random.Random(42)
UTC = datetime.timezone.utc

PRODUCTS = [
    # sku, name, category, price, cost, store, warehouse, reorder
    ('BEV-CC-500', 'Coca Cola 500ml', 'Beverages', 40, 28, 12, 86, 20),
    ('BEV-PE-500', 'Pepsi 500ml', 'Beverages', 40, 28, 64, 120, 20),
    ('SNK-LY-CL', 'Lays Classic', 'Snacks', 30, 20, 18, 95, 25),
    ('SNK-KK-M', 'Kurkure Masala', 'Snacks', 25, 16, 52, 110, 20),
    ('GRC-BS-001', 'Parle Biscuits', 'Grocery', 35, 24, 90, 200, 30),
    ('GRC-RI-1K', 'Basmati Rice 1kg', 'Grocery', 120, 92, 45, 80, 15),
    ('PC-SH-SS', 'Sunsilk Shampoo', 'Personal Care', 150, 110, 28, 60, 12),
    ('PC-SP-LX', 'Lux Soap', 'Personal Care', 45, 30, 0, 40, 25),
    ('HH-DT-SF', 'Surf Detergent', 'Household', 210, 165, 33, 70, 10),
    ('PC-TP-CG', 'Colgate Toothpaste', 'Personal Care', 95, 68, 8, 55, 15),
]

CUSTOMERS = [
    ('Aarav Sharma', '9811000001', 'regular'),
    ('Priya Nair', '9811000002', 'regular'),
    ('Rohan Gupta', '9811000003', 'walk-in'),
    ('Sneha Iyer', '9811000004', 'premium'),
    ('Vikram Singh', '9811000005', 'walk-in'),
    ('Ananya Das', '9811000006', 'regular'),
    ('Karan Mehta', '9811000007', 'premium'),
    ('Divya Rao', '9811000008', 'walk-in'),
    ('Arjun Patel', '9811000009', 'regular'),
    ('Kavya Reddy', '9811000010', 'walk-in'),
    ('Aditya Khan', '9811000011', 'regular'),
    ('Meera Joshi', '9811000012', 'premium'),
    ('Rahul Verma', '9811000013', 'regular'),
    ('Pooja Singh', '9811000014', 'walk-in'),
    ('Nikhil Bose', '9811000015', 'regular'),
    ('Ishita Jain', '9811000016', 'walk-in'),
    ('Varun Malhotra', '9811000017', 'premium'),
    ('Ritu Agarwal', '9811000018', 'regular'),
    ('Sahil Kapoor', '9811000019', 'walk-in'),
    ('Neha Kulkarni', '9811000020', 'regular'),
    ('Amit Tiwari', '9811000021', 'walk-in'),
    ('Farah Sheikh', '9811000022', 'regular'),
    ('Deepak Yadav', '9811000023', 'premium'),
    ('Lakshmi Menon', '9811000024', 'walk-in'),
]

SUPPLIERS = [
    ('FreshBeverage Distributors', 'beverages@freshbev.in', '9812000001', 'Beverages'),
    ('SnackWorld Foods', 'sales@snackworld.in', '9812000002', 'Snacks'),
    ('DailyNeeds Wholesale', 'care@dailyneeds.in', '9812000003', 'Grocery'),
    ('CarePlus Supply Co', 'hello@careplus.in', '9812000004', 'Personal Care'),
]


def get_or_create(db, model, lookup: dict, defaults: dict | None = None):
    obj = db.query(model).filter_by(**lookup).first()
    if obj:
        return obj, False
    obj = model(**{**(defaults or {}), **lookup})
    db.add(obj)
    db.flush()
    return obj, True


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        warehouse, _ = get_or_create(
            db, Warehouse,
            {'code': 'WH-01'},
            {'name': 'Main Warehouse', 'location': 'Industrial Area, Phase 2', 'capacity': 20000},
        )

        EMPLOYEE_ROSTER = [
            # name, email, password, role, status, modules, firebase_uid
            (
                'System Administrator',
                'admin@invintell.com',
                'admin123',
                'admin',
                'active',
                ['*'],
                'CymfrAYNvoQoZp6D6PBcZZE8IV73',
            ),
            (
                'Store Operations Employee',
                'store@invintell.com',
                'storeoperations123',
                'employee',
                'active',
                ['store_monitor', 'customer_analytics', 'spatial_intelligence', 'queue_intelligence', 'alerts'],
                'gRDhAdGw7WSNmYD1gzAkm77uo6X2',
            ),
            (
                'Inventory Employee',
                'inventory@invintell.com',
                'inventory123',
                'employee',
                'active',
                ['products', 'inventory', 'low_stock', 'forecasting', 'exceptions'],
                'AfS18LpKH0WaKNbast3uppJqsFt2',
            ),
            (
                'Warehouse Employee',
                'warehouse@invintell.com',
                'warehouse123',
                'employee',
                'active',
                ['orders', 'allocation', 'picking', 'packing', 'dispatch', 'exceptions'],
                'UOZmYBMOQ5REXoYVTzYZppTgtqn2',
            ),
            (
                'Sales & Billing Employee',
                'sales@invintell.com',
                'salesbilling123',
                'employee',
                'active',
                ['billing_sales', 'products', 'inventory', 'ai_insights', 'alerts'],
                'KMAncMUFZhbGEpC53oagpqYrCRw2',
            ),
            (
                'Reports & Finance Employee',
                'finance@invintell.com',
                'reportsfinance123',
                'employee',
                'active',
                ['finance', 'report_center', 'ai_insights', 'alerts', 'exceptions'],
                '5gWSr2p3ELOU26Cpg3FHPOdZ74g2',
            ),
        ]

        allowed_emails = {row[1] for row in EMPLOYEE_ROSTER}
        # Clean up any legacy extra users not in allowed roster
        db.query(User).filter(~User.email.in_(allowed_emails)).delete(synchronize_session=False)

        for name, email, password, role, status, mods, fb_uid in EMPLOYEE_ROSTER:
            user_obj = db.query(User).filter(User.email == email).first()
            modules_json = json.dumps(mods)
            if not user_obj:
                user_obj = User(
                    name=name,
                    email=email,
                    firebase_uid=fb_uid,
                    hashed_password=get_password_hash(password),
                    role=role,
                    status=status,
                    assigned_modules=modules_json,
                    store='Main Street Store',
                    is_active=(status == 'active'),
                    created_at=datetime.datetime.now(UTC) - datetime.timedelta(days=random.randint(5, 45)),
                    last_login=datetime.datetime.now(UTC) - datetime.timedelta(hours=random.randint(1, 48)) if status == 'active' else None,
                )
                db.add(user_obj)
            else:
                user_obj.name = name
                user_obj.role = role
                user_obj.status = status
                user_obj.assigned_modules = modules_json
                user_obj.firebase_uid = fb_uid
                user_obj.is_active = (status == 'active')
        db.commit()

        products = {}
        for sku, name, category, price, cost, store, wh, reorder in PRODUCTS:
            product, _ = get_or_create(
                db, Product, {'sku': sku},
                {'name': name, 'category': category, 'price': price, 'cost_price': cost, 'unit': 'pcs'},
            )
            products[sku] = product
            inv, created = get_or_create(db, Inventory, {'product_id': product.id}, {})
            if created:
                inv.warehouse_id = warehouse.id
                inv.store_stock = store
                inv.warehouse_stock = wh
                inv.reserved_stock = 0
                inv.reorder_level = reorder
                inv.status = classify_status(store, reorder)

        customers = []
        for name, phone, segment in CUSTOMERS:
            customer, _ = get_or_create(db, Customer, {'phone': phone}, {'name': name, 'segment': segment})
            customers.append(customer)

        for name, contact, phone, category in SUPPLIERS:
            get_or_create(db, Supplier, {'name': name}, {'contact': contact, 'phone': phone, 'category': category})

        _seed_sales(db, products, customers)
        _seed_orders(db, products, customers)
        _seed_risks_alerts(db, products)
        _seed_transfers(db, warehouse, products)
        db.commit()
        print('Seed completed successfully.')
    finally:
        db.close()


def _seed_sales(db, products, customers):
    if db.query(Sale).count():
        return
    skus = list(PRODUCTS)
    weights = [3, 3, 2.4, 2.2, 2, 1.4, 1, 1.2, 0.8, 1.6]  # beverages/snacks sell fastest
    hour_weights = [0.4, 0.2, 0.1, 0.1, 0.2, 0.5, 1, 1.6, 2.2, 2.6, 2.4, 2.8, 3.2, 3.0, 2.6, 2.8, 3.0, 3.6, 4.2, 4.6, 3.8, 2.6, 1.6, 0.9]
    hours = list(range(24))
    now = datetime.datetime.now(UTC)
    bill_seq = 1
    payment_methods = ['UPI', 'UPI', 'UPI', 'Card', 'Card', 'Cash']

    def make_sale(day_offset: int, count: int):
        nonlocal bill_seq
        day = (now - datetime.timedelta(days=day_offset)).date()
        for _ in range(count):
            sku_row = rng.choices(skus, weights=weights, k=1)[0]
            sku, _, _, price, _, _, _, _ = sku_row
            product = products[sku]
            hour = rng.choices(hours, weights=hour_weights, k=1)[0]
            minute = rng.randrange(60)
            sold_at = datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=UTC)
            if day_offset > 0 and sold_at > now:
                continue
            qty = rng.choices([1, 2, 3, 4], weights=[55, 25, 12, 8])[0]
            customer = rng.choice(customers) if rng.random() < 0.85 else None
            db.add(
                Sale(
                    bill_number=f'BILL-{day.strftime("%Y%m%d")}-{bill_seq:05d}',
                    product_id=product.id,
                    customer_id=customer.id if customer else None,
                    quantity=qty,
                    unit_price=price,
                    total_amount=qty * price,
                    payment_method=rng.choice(payment_methods),
                    is_refund=rng.random() < 0.015,
                    sold_at=sold_at,
                )
            )
            bill_seq += 1

    make_sale(0, 186)  # today: 186 transactions
    for ago in range(1, 31):
        make_sale(ago, rng.randint(95, 165))
    db.flush()


def _seed_orders(db, products, customers):
    if db.query(Order).count():
        return
    plan = [('PENDING', 8), ('ALLOCATED', 5), ('PICKING', 4), ('PACKING', 3), ('READY', 2), ('DISPATCHED', 6)]
    skus = list(products.values())
    # Seeded orders must be allocatable: cap quantities at available store stock.
    stock = {sku: store for sku, _, _, _, _, store, _, _ in PRODUCTS}
    seq = 1
    for status, count in plan:
        for _ in range(count):
            customer = rng.choice(customers)
            order = Order(order_number=f'ORD-{seq:05d}', customer_id=customer.id, status=status, total_amount=0)
            db.add(order)
            db.flush()
            total = 0
            picked = rng.sample(skus, k=rng.randint(1, 3))
            added = False
            for item_product in picked:
                available = stock.get(item_product.sku, 0)
                if available <= 0:
                    continue
                qty = min(rng.randint(1, 5), available)
                stock[item_product.sku] = available - qty
                total += item_product.price * qty
                db.add(OrderItem(order_id=order.id, product_id=item_product.id, quantity=qty, unit_price=item_product.price))
                added = True
            if not added:  # fallback to a well-stocked staple
                staple = products['GRC-BS-001']
                total += staple.price
                db.add(OrderItem(order_id=order.id, product_id=staple.id, quantity=1, unit_price=staple.price))
            order.total_amount = total
            seq += 1
    db.flush()


def _seed_risks_alerts(db, products):
    if db.query(Risk).count():
        return
    cola = products['BEV-CC-500']
    now = datetime.datetime.now(UTC)
    risks = [
        {
            'severity': 'CRITICAL', 'title': 'Coca Cola 500ml stock is below reorder level',
            'description': 'Store stock 12 is below reorder level 20. Warehouse holds 86 units — replenishment recommended.',
            'category': 'inventory', 'product_id': cola.id, 'score': 92,
            'action_label': 'Replenish', 'action_path': '/low-stock',
            'meta': {'store_stock': 12, 'reorder_level': 20, 'warehouse_stock': 86},
        },
        {
            'severity': 'HIGH', 'title': 'Checkout queue is increasing',
            'description': 'Evening footfall is pushing queue lengths above baseline.',
            'category': 'queue', 'score': 78,
            'action_label': 'Review Queue', 'action_path': '/queues',
            'meta': {'queue_now': 14, 'queue_avg': 7},
        },
        {
            'severity': 'MEDIUM', 'title': 'Demand for snacks increased 18%',
            'description': 'Snacks velocity is outpacing the 7-day average. Review forecast cover.',
            'category': 'demand', 'score': 64,
            'action_label': 'View Forecast', 'action_path': '/forecasting', 'meta': {},
        },
        {
            'severity': 'CRITICAL', 'title': 'Lux Soap is out of stock in store',
            'description': 'Store stock is 0 with 40 units in the warehouse. Immediate replenishment needed.',
            'category': 'inventory', 'product_id': products['PC-SP-LX'].id, 'score': 95,
            'action_label': 'Replenish', 'action_path': '/low-stock',
            'meta': {'store_stock': 0, 'reorder_level': 25, 'warehouse_stock': 40},
        },
        {
            'severity': 'LOW', 'title': 'Supplier delivery window shifted',
            'description': 'CarePlus Supply Co moved Friday delivery to Saturday morning.',
            'category': 'supplier', 'score': 28,
            'action_label': 'View Suppliers', 'action_path': '/suppliers', 'meta': {},
        },
    ]
    for r in risks:
        meta = r.pop('meta')
        db.add(Risk(status='active', meta_json=json.dumps(meta), created_at=now, **r))

    alerts = [
        ('Morning footfall surge', 'footfall', 'MEDIUM', '/customer-analytics',
         {'customers_current': 42, 'visitors_today': 742, 'peak_hour': '18:00 – 19:00', 'busiest_zone': 'Beverages'}),
        ('Queue building at checkout 2', 'queue', 'HIGH', '/queues', {'queue_length': 8}),
        ('Dwell time holding steady', 'dwell', 'LOW', '/customer-analytics', {'average_dwell_time': '11m 24s'}),
        ('3 beverage SKUs near reorder level', 'inventory', 'HIGH', '/low-stock', {}),
        ('5 orders awaiting allocation', 'orders', 'MEDIUM', '/allocation', {}),
    ]
    for title, category, severity, link, meta in alerts:
        db.add(Alert(title=title, message=json.dumps(meta), category=category, severity=severity, link=link, created_at=now))
    db.flush()


def _seed_transfers(db, warehouse, products):
    if db.query(Transfer).count():
        return
    db.add(Transfer(transfer_number='TRF-00001', warehouse_id=warehouse.id,
                    product_id=products['BEV-PE-500'].id, quantity=50, status='COMPLETED'))
    db.add(Transfer(transfer_number='TRF-00002', warehouse_id=warehouse.id,
                    product_id=products['SNK-KK-M'].id, quantity=40, status='COMPLETED'))
    db.add(Transfer(transfer_number='TRF-00003', warehouse_id=warehouse.id,
                    product_id=products['BEV-CC-500'].id, quantity=30, status='PENDING'))
    db.flush()


if __name__ == '__main__':
    seed()
