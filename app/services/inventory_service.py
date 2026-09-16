from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.inventory import Inventory


def classify_status(store_stock: int, reorder_level: int) -> str:
    if store_stock <= 0:
        return 'Out of Stock'
    if store_stock <= int(reorder_level * 0.5):
        return 'Critical'
    if store_stock <= reorder_level:
        return 'Low Stock'
    return 'Healthy'


def refresh_status(inv: Inventory) -> Inventory:
    inv.status = classify_status(inv.store_stock or 0, inv.reorder_level or 0)
    return inv


def get_enriched_inventory(
    db: Session,
    status: str | None = None,
    category: str | None = None,
    risk_type: str | None = None,
    demand_level: str | None = None,
    period_days: int | None = 30,
    search: str | None = None,
) -> list[dict]:
    from sqlalchemy import func
    from app.models.product import Product
    from app.models.sale import Sale

    # Build sales query with optional period cutoff
    sales_q = db.query(
        Sale.product_id,
        func.coalesce(func.sum(Sale.quantity), 0).label('units'),
        func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
        func.count(func.distinct(func.date(Sale.sold_at))).label('days'),
    ).filter(Sale.is_refund.is_(False))

    if period_days and period_days > 0:
        max_sale_date = db.query(func.max(Sale.sold_at)).scalar()
        if max_sale_date:
            cutoff = max_sale_date - timedelta(days=period_days)
            sales_q = sales_q.filter(Sale.sold_at >= cutoff)

    sales_rows = sales_q.group_by(Sale.product_id).all()
    sales_map = {
        r[0]: {
            'units': int(r[1] or 0),
            'revenue': round(float(r[2] or 0), 2),
            'days': max(int(r[3] or 1), 1),
        }
        for r in sales_rows
    }

    q = db.query(Inventory).join(Product, Product.id == Inventory.product_id)
    if status and status != 'All':
        if status in ('Low Stock', 'Low'):
            q = q.filter(Inventory.status.in_(['Low', 'Low Stock']))
        else:
            q = q.filter(Inventory.status == status)
    if category and category != 'All':
        q = q.filter(Product.category == category)
    if search:
        s_term = f"%{search.strip().lower()}%"
        q = q.filter(
            func.lower(Product.name).like(s_term)
            | func.lower(Product.sku).like(s_term)
            | func.lower(Product.category).like(s_term)
        )

    rows = q.order_by(Product.name).all()
    out = []
    for inv in rows:
        p = inv.product
        s_info = sales_map.get(inv.product_id, {'units': 0, 'revenue': 0.0, 'days': 1})
        units = s_info['units']
        rev = s_info['revenue']
        has_demand_data = inv.product_id in sales_map
        vel = round(units / s_info['days'], 2) if (has_demand_data and units > 0) else (0.0 if has_demand_data else None)

        store_st = inv.store_stock or 0
        wh_st = inv.warehouse_stock or 0
        tot_st = store_st + wh_st
        reorder = inv.reorder_level or 20

        # Consistent status classification
        if store_st <= 0:
            norm_status = 'Out of Stock'
            severity = 'Critical'
        elif store_st <= int(reorder * 0.5):
            norm_status = 'Critical'
            severity = 'Critical'
        elif store_st <= reorder:
            norm_status = 'Low Stock'
            severity = 'High'
        elif store_st <= int(reorder * 1.3):
            norm_status = 'Healthy'
            severity = 'Medium'
        else:
            norm_status = 'Healthy'
            severity = 'Low'

        # Days of stock left based on real daily velocity
        if vel and vel > 0:
            days_left = round(store_st / vel, 1)
        elif store_st > 0:
            days_left = None
        else:
            days_left = 0.0

        # Demand level classification
        if vel and vel >= 2.0:
            d_level = 'High Demand'
            demand_risk = 'High' if store_st <= reorder else 'Medium'
        elif vel and vel >= 1.0:
            d_level = 'Medium Demand'
            demand_risk = 'Medium' if store_st <= reorder else 'Low'
        elif vel and vel > 0:
            d_level = 'Low Demand'
            demand_risk = 'Low'
        else:
            d_level = 'No Recent Demand'
            demand_risk = 'Low'

        # Comprehensive Risk Type Classification (Low, Critical, OOS, Slow Moving, Dead Stock)
        if store_st <= 0:
            r_type = 'Out of Stock'
            rec_priority = 'Critical'
        elif store_st <= int(reorder * 0.5):
            r_type = 'Critical'
            rec_priority = 'Critical'
        elif store_st <= reorder:
            r_type = 'Low Stock'
            rec_priority = 'High'
        elif units == 0 or vel is None or vel == 0:
            r_type = 'Dead Stock'
            rec_priority = 'High' if (store_st * p.price) >= 5000 else 'Medium'
        elif (days_left is not None and days_left >= 45.0) or (vel and vel < 1.25):
            r_type = 'Slow Moving'
            rec_priority = 'Medium' if (store_st * p.price) >= 5000 else 'Low'
        else:
            r_type = 'Healthy'
            rec_priority = 'Low'

        # Filter by risk_type if requested
        if risk_type and risk_type != 'All' and r_type != risk_type:
            continue
        # Filter by demand_level if requested
        if demand_level and demand_level != 'All' and d_level != demand_level:
            continue

        # Recommended replenishment units
        target_stock = max(reorder * 2, int((vel or 1.5) * 14))
        rec_rep = max(0, target_stock - store_st) if (store_st <= reorder or severity in ('Critical', 'High')) else 0
        if rec_rep > 0 and wh_st > 0:
            rec_rep = min(rec_rep, wh_st)
        elif rec_rep == 0 and store_st <= reorder:
            rec_rep = max(10, reorder - store_st)

        # Deterministic EAN-13 barcode
        code12 = f"890{inv.product_id:09d}"
        evens = sum(int(code12[i]) for i in range(1, 12, 2))
        odds = sum(int(code12[i]) for i in range(0, 12, 2))
        chk = (10 - ((odds + evens * 3) % 10)) % 10
        barcode = f"{code12}{chk}"

        inv_value = round(tot_st * p.price, 2)
        store_val = round(store_st * p.price, 2)

        # Structured Explainable AI Recommendation
        if r_type == 'Out of Stock':
            ai_rec = {
                'action': f"Priority Replenish ({rec_rep} units)",
                'strategy': 'Replenish',
                'discount_pct': 0,
                'promotional_price': round(p.price, 2),
                'reason': f"Stock is depleted (0 units). Historical sales velocity is {vel or 1.5} pcs/day. Immediate central warehouse transfer required.",
                'priority': 'Critical',
                'expected_objective': 'Recover Lost Sales & Prevent Customer Dropoff',
                'capital_at_risk': round(rec_rep * p.price, 2),
            }
        elif r_type == 'Critical':
            ai_rec = {
                'action': f"Emergency Restock ({rec_rep} units)",
                'strategy': 'Replenish',
                'discount_pct': 0,
                'promotional_price': round(p.price, 2),
                'reason': f"Store stock is critically low ({store_st} pcs left, ~{days_left} days cover). High demand velocity ({vel or 1.5} pcs/day). Do not discount.",
                'priority': 'Critical',
                'expected_objective': 'Avoid Imminent Shelf Out-of-Stock',
                'capital_at_risk': store_val,
            }
        elif r_type == 'Low Stock':
            ai_rec = {
                'action': f"Restock ({rec_rep} units)",
                'strategy': 'Replenish',
                'discount_pct': 0,
                'promotional_price': round(p.price, 2),
                'reason': f"Store inventory ({store_st} pcs) is below reorder threshold ({reorder} pcs). Replenish from warehouse to maintain optimal shelf density.",
                'priority': 'High',
                'expected_objective': 'Maintain Shelf Buffer',
                'capital_at_risk': store_val,
            }
        elif r_type == 'Dead Stock':
            disc = 20 if store_val >= 8000 else 15
            ai_rec = {
                'action': f"{disc}% Clearance Markdown",
                'strategy': 'Clearance',
                'discount_pct': disc,
                'promotional_price': round(p.price * (1 - disc / 100), 2),
                'reason': f"Zero sales activity in past {period_days or 30} days with ₹{store_val:,.0f} working capital tied up in {store_st} idle units. Clearance markdown recommended to stimulate initial velocity.",
                'priority': 'High' if store_val >= 8000 else 'Medium',
                'expected_objective': 'Liquidate Idle Capital & Free Shelf Space',
                'capital_at_risk': store_val,
            }
        elif r_type == 'Slow Moving':
            if p.price >= 20.0:
                disc = 10
                ai_rec = {
                    'action': '10% Promotional Markdown',
                    'strategy': 'Promotion',
                    'discount_pct': disc,
                    'promotional_price': round(p.price * 0.9, 2),
                    'reason': f"Extensive stock cover ({days_left} days) with sluggish burn rate ({vel} pcs/day). Introduce a 10% promotional tag or shelf talker to accelerate sell-through.",
                    'priority': 'Medium',
                    'expected_objective': 'Accelerate Sell-Through Pace',
                    'capital_at_risk': store_val,
                }
            else:
                ai_rec = {
                    'action': 'Bundle with Top Seller',
                    'strategy': 'Bundle',
                    'discount_pct': 10,
                    'promotional_price': round(p.price * 0.9, 2),
                    'reason': f"Sub-optimal turnover ({vel} pcs/day, {days_left} days cover). Cross-merchandise or create a 'Buy Together' bundle with fast-moving category items.",
                    'priority': 'Medium',
                    'expected_objective': 'Cross-Sell Basket Building',
                    'capital_at_risk': store_val,
                }
        else:
            ai_rec = {
                'action': 'Maintain Stock Buffer',
                'strategy': 'Monitor',
                'discount_pct': 0,
                'promotional_price': round(p.price, 2),
                'reason': f"Inventory levels ({store_st} pcs) and sales velocity ({vel} pcs/day) are well balanced. Regular operational monitoring.",
                'priority': 'Low',
                'expected_objective': 'Equilibrium Maintenance',
                'capital_at_risk': 0.0,
            }

        out.append({
            'id': inv.id,
            'product_id': inv.product_id,
            'name': p.name if p else f"Product #{inv.product_id}",
            'sku': p.sku if p else f"SKU-{inv.product_id}",
            'category': p.category if p else 'General Merchandise',
            'department': p.department if p else None,
            'price': p.price if p else 0.0,
            'cost_price': p.cost_price if p else 0.0,
            'store_stock': store_st,
            'warehouse_stock': wh_st,
            'total_stock': tot_st,
            'reserved_stock': inv.reserved_stock or 0,
            'available_stock': inv.available_stock,
            'reorder_level': reorder,
            'status': norm_status,
            'severity': severity,
            'risk_type': r_type,
            'demand_level': d_level,
            'units_sold': units,
            'revenue': rev,
            'sales_velocity': vel,
            'days_of_stock': days_left,
            'demand_risk': demand_risk,
            'recommended_replenishment': rec_rep,
            'barcode': barcode,
            'has_demand_data': has_demand_data,
            'inventory_value': inv_value,
            'store_value': store_val,
            'ai_recommendation': ai_rec,
        })
    return out


def get_low_stock_matrix(
    db: Session,
    category: str | None = None,
    severity: str | None = None,
    risk_type: str | None = None,
    demand_risk: str | None = None,
    demand_level: str | None = None,
    period_days: int | None = 30,
    search: str | None = None,
) -> list[dict]:
    items = get_enriched_inventory(
        db,
        category=category,
        risk_type=risk_type,
        demand_level=demand_level,
        period_days=period_days,
        search=search,
    )
    filtered = []
    for item in items:
        # Include all items with any identified inventory risk (unless filtered to specific risk_type)
        is_at_risk = (
            item['risk_type'] in ('Low Stock', 'Critical', 'Out of Stock', 'Slow Moving', 'Dead Stock')
            or item['status'] in ('Low Stock', 'Low', 'Critical', 'Out of Stock')
            or item['store_stock'] <= item['reorder_level']
        )
        if not is_at_risk:
            continue
        if severity and severity != 'All' and item['severity'] != severity:
            continue
        if demand_risk and demand_risk != 'All' and item['demand_risk'] != demand_risk:
            continue
        filtered.append(item)

    # Sort: Critical & OOS first, then Dead Stock & Slow Moving by capital at risk, then by days of stock
    def sort_score(x):
        r = x['risk_type']
        if r == 'Out of Stock':
            return (0, 0)
        if r == 'Critical':
            return (1, x['days_of_stock'] if x['days_of_stock'] is not None else 999)
        if r == 'Low Stock':
            return (2, x['days_of_stock'] if x['days_of_stock'] is not None else 999)
        if r == 'Dead Stock':
            return (3, -x['store_value'])
        if r == 'Slow Moving':
            return (4, -x['store_value'])
        return (5, 999)

    filtered.sort(key=sort_score)
    return filtered


def get_inventory_summary(db: Session, period_days: int | None = 30) -> dict:
    items = get_enriched_inventory(db, period_days=period_days)
    total_products = len(items)
    total_store = sum(i['store_stock'] for i in items)
    total_warehouse = sum(i['warehouse_stock'] for i in items)
    total_units = total_store + total_warehouse
    total_value = round(sum(i['total_stock'] * i['price'] for i in items), 2)
    store_value = round(sum(i['store_stock'] * i['price'] for i in items), 2)

    healthy_count = sum(1 for i in items if i['risk_type'] == 'Healthy')
    low_stock_count = sum(1 for i in items if i['risk_type'] == 'Low Stock')
    critical_count = sum(1 for i in items if i['risk_type'] == 'Critical')
    out_of_stock_count = sum(1 for i in items if i['risk_type'] == 'Out of Stock')
    slow_moving_count = sum(1 for i in items if i['risk_type'] == 'Slow Moving')
    dead_stock_count = sum(1 for i in items if i['risk_type'] == 'Dead Stock')

    dead_stock_val = round(sum(i['store_value'] for i in items if i['risk_type'] == 'Dead Stock'), 2)
    slow_moving_val = round(sum(i['store_value'] for i in items if i['risk_type'] == 'Slow Moving'), 2)

    # Category breakdown
    cat_map = {}
    for i in items:
        c = i['category']
        if c not in cat_map:
            cat_map[c] = {'category': c, 'count': 0, 'units': 0, 'value': 0.0}
        cat_map[c]['count'] += 1
        cat_map[c]['units'] += i['total_stock']
        cat_map[c]['value'] += round(i['total_stock'] * i['price'], 2)

    category_breakdown = sorted(cat_map.values(), key=lambda x: x['units'], reverse=True)
    categories = sorted(list(cat_map.keys()))

    return {
        'total_products': total_products,
        'total_units': total_units,
        'store_stock': total_store,
        'warehouse_stock': total_warehouse,
        'inventory_value': total_value,
        'store_value': store_value,
        'healthy': healthy_count,
        'low_stock': low_stock_count,
        'critical': critical_count,
        'out_of_stock': out_of_stock_count,
        'slow_moving': slow_moving_count,
        'dead_stock': dead_stock_count,
        'dead_stock_value': dead_stock_val,
        'slow_moving_value': slow_moving_val,
        'categories': categories,
        'category_breakdown': category_breakdown,
        'health_distribution': [
            {'name': 'Healthy', 'value': healthy_count, 'color': '#10B981'},
            {'name': 'Low Stock', 'value': low_stock_count, 'color': '#F59E0B'},
            {'name': 'Critical', 'value': critical_count, 'color': '#EF4444'},
            {'name': 'Out of Stock', 'value': out_of_stock_count, 'color': '#64748B'},
            {'name': 'Slow Moving', 'value': slow_moving_count, 'color': '#F97316'},
            {'name': 'Dead Stock', 'value': dead_stock_count, 'color': '#8B5CF6'},
        ],
    }


def replenish(db: Session, product_id: int, quantity: int) -> Inventory:
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        return None
    # Deduct from warehouse and add to store stock
    wh = inv.warehouse_stock or 0
    actual_transfer = min(quantity, wh) if wh > 0 else quantity
    if wh > 0:
        inv.warehouse_stock = max(0, wh - actual_transfer)
    inv.store_stock = (inv.store_stock or 0) + actual_transfer
    inv = refresh_status(inv)
    db.commit()
    db.refresh(inv)
    return inv
