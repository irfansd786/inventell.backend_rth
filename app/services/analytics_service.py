"""Real dataset analytics service calculations from M5 & Retail Inventory."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.product import Product
from app.models.sale import Sale
from app.services.dashboard_service import _get_dataset_anchor_date, _sales_totals, _utc_day_bounds


def get_kpis(db: Session) -> dict:
    anchor_date = _get_dataset_anchor_date(db)
    min_date = db.query(func.min(Sale.sold_at)).scalar()
    
    total_rev, total_orders, total_units = (
        db.query(
            func.coalesce(func.sum(Sale.total_amount), 0),
            func.count(func.distinct(Sale.bill_number)),
            func.coalesce(func.sum(Sale.quantity), 0),
        )
        .filter(Sale.is_refund.is_(False))
        .first()
    )
    
    product_count = db.query(Product).count()
    category_count = db.query(func.count(func.distinct(Product.category))).scalar() or 0
    inv_val = (
        db.query(func.coalesce(func.sum((Inventory.store_stock + Inventory.warehouse_stock) * Product.price), 0))
        .select_from(Inventory)
        .join(Product, Product.id == Inventory.product_id)
        .first()[0]
    )

    t_start, t_end = _utc_day_bounds(db, 0)
    today = _sales_totals(db, t_start, t_end)

    return {
        "analysis_date": anchor_date.strftime("%Y-%m-%d"),
        "analysis_date_formatted": anchor_date.strftime("%d %b %Y"),
        "dataset_period": f"{min_date.strftime('%d %b %Y') if min_date else ''} – {anchor_date.strftime('%d %b %Y')}",
        "total_revenue": round(float(total_rev or 0), 2),
        "total_transactions": int(total_orders or 0),
        "total_units_sold": int(total_units or 0),
        "active_products": product_count,
        "active_categories": category_count,
        "inventory_valuation": round(float(inv_val or 0), 2),
        "today_revenue": round(today["revenue"], 2),
        "today_transactions": today["transactions"],
        "today_units": today["units"],
        "avg_order_value": round(float(total_rev or 0) / max(int(total_orders or 1), 1), 2),
    }


def get_revenue_trend(db: Session, days: int = 30) -> list:
    points = []
    for ago in range(days - 1, -1, -1):
        start, end = _utc_day_bounds(db, ago)
        rev, orders, units = (
            db.query(
                func.coalesce(func.sum(Sale.total_amount), 0),
                func.count(func.distinct(Sale.bill_number)),
                func.coalesce(func.sum(Sale.quantity), 0),
            )
            .filter(Sale.sold_at >= start, Sale.sold_at < end, Sale.is_refund.is_(False))
            .first()
        )
        points.append({
            "date": start.strftime("%Y-%m-%d"),
            "label": start.strftime("%d %b"),
            "revenue": round(float(rev or 0), 2),
            "transactions": int(orders or 0),
            "units": int(units or 0),
        })
    return points


def get_category_performance(db: Session) -> list:
    rows = (
        db.query(
            Product.category,
            func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
            func.coalesce(func.sum(Sale.quantity), 0).label('units'),
            func.count(func.distinct(Product.id)).label('product_count'),
        )
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.is_refund.is_(False))
        .group_by(Product.category)
        .order_by(func.sum(Sale.total_amount).desc())
        .all()
    )
    total_rev = sum(float(r[1] or 0) for r in rows) or 1.0
    return [
        {
            "category": r[0],
            "revenue": round(float(r[1] or 0), 2),
            "units": int(r[2] or 0),
            "products": int(r[3] or 0),
            "share_pct": round(float(r[1] or 0) / total_rev * 100, 1),
        }
        for r in rows
    ]
def get_key_insights(db: Session) -> list:
    cat_perf = get_category_performance(db)
    top_cat = cat_perf[0] if cat_perf else {"category": "Foods", "share_pct": 50.0}

    low_count = db.query(Inventory).filter(Inventory.status.in_(['Low', 'Critical'])).count()
    low_example = (
        db.query(Product.name)
        .join(Inventory, Inventory.product_id == Product.id)
        .filter(Inventory.status.in_(['Low', 'Critical']))
        .order_by(Inventory.store_stock.asc())
        .first()
    )
    rischest_cat = (
        db.query(Product.category, func.count(Inventory.id))
        .join(Inventory, Inventory.product_id == Product.id)
        .filter(Inventory.status.in_(['Low', 'Critical']))
        .group_by(Product.category)
        .order_by(func.count(Inventory.id).desc())
        .first()
    )

    return [
        {
            "id": 1,
            "metric": "Category Performance",
            "severity": "info",
            "title": f"Category Leader: {top_cat['category']}",
            "description": f"{top_cat['category']} represents "
            f"{top_cat.get('share_pct', 0)}% of total retail sales volume in historical analysis.",
            "explanation": f"{top_cat['category']} represents "
            f"{top_cat.get('share_pct', 0)}% of total retail sales volume in historical analysis.",
            "recommendedAction": f"Prioritize shelf availability and replenishment for {top_cat['category']}.",
            "relatedPath": "/analytics",
            "impact": "High Volume Driver",
        },
        {
            "id": 2,
            "metric": "Inventory Risk",
            "severity": "high" if low_count > 0 else "info",
            "title": f"{low_count} products at low/critical stock",
            "description": (
                f"Lowest cover: {low_example[0]}. "
                f"Highest-risk category: {rischest_cat[0]} ({rischest_cat[1]} items)."
                if low_example and rischest_cat else
                "No low-stock products in the current inventory snapshot."
            ),
            "explanation": (
                f"Lowest cover: {low_example[0]}. "
                f"Highest-risk category: {rischest_cat[0]} ({rischest_cat[1]} items)."
                if low_example and rischest_cat else
                "No low-stock products in the current inventory snapshot."
            ),
            "recommendedAction": "Review replenishment requirements and create warehouse transfers.",
            "relatedPath": "/low-stock",
            "impact": "Stockout Protection",
        },
        {
            "id": 3,
            "metric": "Buffer Protection",
            "severity": "info",
            "title": "Warehouse buffer active",
            "description": "Central warehouse holds buffer multiples of store stock to protect against retail stockouts.",
            "explanation": "Central warehouse holds buffer multiples of store stock to protect against retail stockouts.",
            "recommendedAction": "Keep safety buffers aligned with forecasted demand.",
            "relatedPath": "/warehouse",
            "impact": "SLA & Availability",
        },
    ]


def hourly_sales_today(db: Session) -> list:
    """Revenue + bill counts per hour for the anchor (latest dataset) day."""
    from app.services.dashboard_service import _utc_day_bounds
    start, end = _utc_day_bounds(db, 0)
    rows = (
        db.query(
            func.strftime('%H', Sale.sold_at).label('hh'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
            func.count(func.distinct(Sale.bill_number)).label('orders'),
        )
        .filter(Sale.sold_at >= start, Sale.sold_at < end, Sale.is_refund.is_(False))
        .group_by('hh')
        .order_by('hh')
        .all()
    )
    return [
        {'hour': f'{r[0]}:00', 'revenue': round(float(r[1]), 2), 'orders': int(r[2])}
        for r in rows
    ]


def inventory_turnover(db: Session) -> list:
    """Per-category turnover: lifetime units sold vs current system stock."""
    rows = (
        db.query(
            Product.category,
            func.coalesce(func.sum(Sale.quantity), 0).label('units_sold'),
        )
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.is_refund.is_(False))
        .group_by(Product.category)
        .all()
    )
    stock_rows = dict(
        db.query(
            Product.category,
            func.coalesce(
                func.sum(func.coalesce(Inventory.store_stock, 0)
                         + func.coalesce(Inventory.warehouse_stock, 0)), 0),
        )
        .join(Inventory, Inventory.product_id == Product.id)
        .group_by(Product.category)
        .all()
    )
    out = []
    for category, units in rows:
        stock = int(stock_rows.get(category, 0))
        out.append({
            'category': category,
            'units_sold': int(units),
            'system_stock': stock,
            'turnover_ratio': round(int(units) / stock, 2) if stock else 0,
        })
    return sorted(out, key=lambda r: r['turnover_ratio'], reverse=True)