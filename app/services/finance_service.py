"""Financial read-models for /api/finance/* — 100% derived from Sale/Product rows.

No hardcoded totals: every number is aggregated from the ingested M5 +
Retail Inventory datasets. The response includes its period + source so the
UI can label it honestly as a historical dataset (never "today's sales").
"""

import calendar
import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.sale import Sale

DATASET_LABEL = 'M5 + Retail Inventory (historical)'


def _period(db: Session) -> dict:
    lo = db.query(func.min(Sale.sold_at)).scalar()
    hi = db.query(func.max(Sale.sold_at)).scalar()
    return {
        'start': lo.isoformat() if lo else '',
        'end': hi.isoformat() if hi else '',
        'label': (
            f"{lo.strftime('%d %b %Y')} – {hi.strftime('%d %b %Y')}"
            if lo and hi else 'No sales data'
        ),
        'source': DATASET_LABEL,
    }


def get_summary(db: Session) -> dict:
    gross = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.is_refund.is_(False)).scalar() or 0
    refunds = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.is_refund.is_(True)).scalar() or 0
    net = gross - refunds
    orders = db.query(func.count(func.distinct(Sale.bill_number))).scalar() or 0
    units = db.query(func.coalesce(func.sum(Sale.quantity), 0)).filter(
        Sale.is_refund.is_(False)).scalar() or 0

    cogs = (
        db.query(func.coalesce(func.sum(Sale.quantity * Product.cost_price), 0))
        .join(Product, Product.id == Sale.product_id)
        .filter(Sale.is_refund.is_(False))
        .scalar() or 0
    )
    gross_margin = round((gross - cogs) / gross * 100, 1) if gross else 0
    net_margin = round((net - cogs) / net * 100, 1) if net else 0

    pay_rows = (
        db.query(Sale.payment_method, func.coalesce(func.sum(Sale.total_amount), 0))
        .filter(Sale.is_refund.is_(False))
        .group_by(Sale.payment_method)
        .all()
    )
    pay_total = sum(float(r[1]) for r in pay_rows) or 1
    payments = [
        {
            'name': (r[0] or 'Unknown'),
            'amount': round(float(r[1]), 2),
            'value': round(float(r[1]) / pay_total * 100, 1),
        }
        for r in sorted(pay_rows, key=lambda r: float(r[1]), reverse=True)
    ]

    monthly = (
        db.query(
            func.strftime('%Y-%m', Sale.sold_at).label('ym'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('total'),
        )
        .group_by('ym')
        .order_by('ym')
        .all()
    )
    # Refunds per month for net series.
    monthly_ref = dict(
        db.query(
            func.strftime('%Y-%m', Sale.sold_at).label('ym'),
            func.coalesce(func.sum(Sale.total_amount), 0),
        )
        .filter(Sale.is_refund.is_(True))
        .group_by('ym')
        .all()
    )
    trend = []
    for ym, total in monthly[-6:]:
        try:
            y, m = ym.split('-')
            label = f'{calendar.month_abbr[int(m)]} {y[2:]}'
        except (ValueError, IndexError):
            label = ym
        ref = float(monthly_ref.get(ym, 0))
        trend.append({
            'month': label,
            'gross': round(float(total), 2),
            'net': round(float(total) - ref, 2),
        })

    top_rows = (
        db.query(
            Product.name,
            Product.sku,
            Product.category,
            Product.price,
            Product.cost_price,
            func.coalesce(func.sum(Sale.quantity), 0).label('units'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
        )
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.is_refund.is_(False))
        .group_by(Product.id)
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(8)
        .all()
    )
    top = [
        {
            'name': r[0],
            'sku': r[1],
            'category': r[2],
            'unitsSold': int(r[5]),
            'revenue': round(float(r[6]), 2),
            'margin': (
                f"{round((float(r[3] or 0) - float(r[4] or 0)) / float(r[3]) * 100, 1)}%"
                if r[3] else '—'
            ),
        }
        for r in top_rows
    ]

    return {
        'period': _period(db),
        'gross': round(float(gross), 2),
        'refunds': round(float(refunds), 2),
        'net': round(float(net), 2),
        'orders': int(orders),
        'units': int(units),
        'grossMarginPct': gross_margin,
        'netMarginPct': net_margin,
        'payments': payments,
        'trend': trend,
        'topProducts': top,
    }
