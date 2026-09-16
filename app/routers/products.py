import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.sale import Sale
from app.schemas.product import ProductIn, ProductOut, ProductUpdate

router = APIRouter(prefix='/products', tags=['products'])


@router.get('/catalog')
def get_catalog(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    products = db.query(Product).order_by(Product.name).all()
    inventories = {i.product_id: i for i in db.query(Inventory).all()}

    # Aggregate sales by product
    sales_rows = (
        db.query(
            Sale.product_id,
            func.coalesce(func.sum(Sale.quantity), 0).label('units'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
            func.count(func.distinct(func.date(Sale.sold_at))).label('days'),
        )
        .filter(Sale.is_refund.is_(False))
        .group_by(Sale.product_id)
        .all()
    )
    sales_map = {
        r[0]: {'units': int(r[1] or 0), 'revenue': round(float(r[2] or 0), 2), 'days': max(int(r[3] or 1), 1)}
        for r in sales_rows
    }

    # Find sales performance percentiles
    all_units = sorted([v['units'] for v in sales_map.values() if v['units'] > 0], reverse=True)
    top_cutoff = all_units[int(len(all_units) * 0.25)] if all_units else 100
    mid_cutoff = all_units[int(len(all_units) * 0.65)] if all_units else 20

    catalog = []
    for p in products:
        inv = inventories.get(p.id)
        store_st = inv.store_stock if inv else 0
        wh_st = inv.warehouse_stock if inv else 0
        tot_st = store_st + wh_st
        reorder = inv.reorder_level if inv else 20

        if tot_st <= 0:
            stock_status = 'Out of Stock'
        elif store_st <= int(reorder * 0.5):
            stock_status = 'Critical'
        elif store_st <= reorder:
            stock_status = 'Low Stock'
        else:
            stock_status = 'Healthy'

        s_info = sales_map.get(p.id, {'units': 0, 'revenue': 0.0, 'days': 1})
        units = s_info['units']
        rev = s_info['revenue']
        velocity = round(units / s_info['days'], 2) if units > 0 else 0.0

        if units == 0:
            sales_perf = 'No Sales'
        elif units >= top_cutoff:
            sales_perf = 'Top Sellers'
        elif units >= mid_cutoff:
            sales_perf = 'High Demand'
        else:
            sales_perf = 'Low Demand'

        catalog.append({
            'id': p.id,
            'sku': p.sku,
            'name': p.name,
            'category': p.category,
            'department': p.department,
            'price': p.price,
            'cost_price': p.cost_price,
            'unit': p.unit,
            'dataset_source': p.dataset_source,
            'is_active': p.is_active,
            'barcode': None,
            'store_stock': store_st,
            'warehouse_stock': wh_st,
            'total_stock': tot_st,
            'reorder_level': reorder,
            'stock_status': stock_status,
            'units_sold': units,
            'revenue': rev,
            'sales_velocity': velocity,
            'sales_performance': sales_perf,
        })

    return catalog


@router.get('/summary')
def get_product_summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    total_products = db.query(Product).count()
    active_products = db.query(Product).filter(Product.is_active.is_(True)).count()
    unique_skus = db.query(func.count(func.distinct(Product.sku))).filter(Product.is_active.is_(True)).scalar() or 0

    inv_totals = db.query(
        func.coalesce(func.sum(Inventory.warehouse_stock), 0).label('wh_units'),
        func.coalesce(func.sum(Inventory.store_stock), 0).label('store_units'),
    ).join(Product, Product.id == Inventory.product_id).filter(Product.is_active.is_(True)).first()

    wh_units = int(inv_totals.wh_units if inv_totals else 0)
    store_units = int(inv_totals.store_units if inv_totals else 0)
    total_units = wh_units + store_units

    effective_products = active_products if active_products > 0 else total_products

    return {
        'total_products': effective_products,
        'active_products': effective_products,
        'total_skus': unique_skus if unique_skus > 0 else effective_products,
        'total_units': total_units,
        'warehouse_units': wh_units,
        'store_units': store_units,
    }


@router.get('/kpis')
def get_product_kpis(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    catalog = get_catalog(db, _user)
    total_products = len(catalog)
    active_products = sum(1 for p in catalog if p['is_active'])
    low_stock = sum(1 for p in catalog if p['stock_status'] in ('Low Stock', 'Critical', 'Out of Stock'))
    
    top_p = max(catalog, key=lambda x: x['revenue']) if catalog else None
    top_seller = {
        'id': top_p['id'],
        'name': top_p['name'],
        'sku': top_p['sku'],
        'revenue': top_p['revenue'],
        'units': top_p['units_sold'],
    } if top_p else None

    return {
        'total_products': total_products,
        'active_products': active_products,
        'low_stock': low_stock,
        'top_seller': top_seller,
    }


@router.get('/{product_id}/details')
def get_product_details(product_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail='Product not found')

    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    store_st = inv.store_stock if inv else 0
    wh_st = inv.warehouse_stock if inv else 0
    tot_st = store_st + wh_st
    reorder = inv.reorder_level if inv else 20

    if tot_st <= 0:
        stock_status = 'Out of Stock'
    elif store_st <= int(reorder * 0.5):
        stock_status = 'Critical'
    elif store_st <= reorder:
        stock_status = 'Low Stock'
    else:
        stock_status = 'Healthy'

    sales = (
        db.query(Sale)
        .filter(Sale.product_id == product_id, Sale.is_refund.is_(False))
        .order_by(Sale.sold_at.asc())
        .all()
    )

    tot_units = sum(s.quantity for s in sales)
    tot_revenue = round(sum(s.total_amount for s in sales), 2)
    distinct_days = len({s.sold_at.date() if hasattr(s.sold_at, 'date') else str(s.sold_at)[:10] for s in sales})
    velocity = round(tot_units / max(distinct_days, 1), 2) if tot_units > 0 else 0.0

    daily_sales = {}
    for s in sales:
        d_val = s.sold_at.date() if hasattr(s.sold_at, 'date') else str(s.sold_at)[:10]
        d_key = d_val if isinstance(d_val, str) else d_val.strftime('%Y-%m-%d')
        if d_key not in daily_sales:
            daily_sales[d_key] = {'units': 0, 'revenue': 0.0}
        daily_sales[d_key]['units'] += s.quantity
        daily_sales[d_key]['revenue'] += s.total_amount

    trend_points = [
        {
            'date': k,
            'label': datetime.datetime.strptime(k, '%Y-%m-%d').strftime('%d %b'),
            'units': v['units'],
            'revenue': round(v['revenue'], 2),
        }
        for k, v in sorted(daily_sales.items())
    ]
    if len(trend_points) > 30:
        trend_points = trend_points[-30:]

    customer_activity = {
        'available': False,
        'message': 'Customer activity mapping unavailable.',
        'details': 'Product-to-camera zone telemetry requires physical shelf coordinate mapping.',
    }

    return {
        'id': p.id,
        'sku': p.sku,
        'name': p.name,
        'category': p.category,
        'department': p.department,
        'price': p.price,
        'cost_price': p.cost_price,
        'unit': p.unit,
        'dataset_source': p.dataset_source,
        'is_active': p.is_active,
        'barcode': None,
        'store_stock': store_st,
        'warehouse_stock': wh_st,
        'total_stock': tot_st,
        'reorder_level': reorder,
        'stock_status': stock_status,
        'units_sold': tot_units,
        'revenue': tot_revenue,
        'sales_velocity': velocity,
        'sales_trend': trend_points,
        'customer_activity': customer_activity,
    }


@router.get('', response_model=list[ProductOut])
def list_products(
    q: str | None = None, limit: int = 100, db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    query = db.query(Product).filter(Product.is_active.is_(True))
    if q:
        like = f'%{q}%'
        query = query.filter((Product.name.ilike(like)) | (Product.sku.ilike(like)))
    return query.order_by(Product.name).limit(min(limit, 500)).all()


@router.get('/{product_id}', response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found')
    return product


@router.post('', response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductIn,
    db: Session = Depends(get_db),
    _user=Depends(require_roles('ADMIN', 'MANAGER')),
):
    if db.query(Product).filter(Product.sku == payload.sku).first():
        raise HTTPException(status_code=409, detail='SKU already exists')
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put('/{product_id}', response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles('ADMIN', 'MANAGER')),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete('/{product_id}')
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_roles('ADMIN', 'MANAGER')),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail='Product not found')
    product.is_active = False
    db.commit()
    return {'status': 'deleted'}
