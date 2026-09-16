"""Sales read-models for /api/sales/*."""

import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.sale import Sale
from app.services.dashboard_service import _sales_totals, _utc_day_bounds, get_revenue_series


def get_summary(db: Session) -> dict:
    start, end = _utc_day_bounds(db, 0)
    t = _sales_totals(db, start, end)
    net = round(t['revenue'] - t['refunds'], 2)
    return {
        'revenue': round(t['revenue'], 2),
        'orders': t['orders'],
        'units_sold': t['units'],
        'average_order_value': round(t['revenue'] / t['orders'], 2) if t['orders'] else 0,
        'refunds': round(t['refunds'], 2),
        'net_revenue': net,
    }


def get_today(db: Session) -> dict:
    start, end = _utc_day_bounds(db, 0)
    rows = (
        db.query(Sale)
        .filter(Sale.sold_at >= start, Sale.sold_at < end)
        .order_by(Sale.sold_at.desc())
        .limit(100)
        .all()
    )
    return {
        'count': len(rows),
        'items': [
            {
                'id': s.id,
                'bill_number': s.bill_number,
                'product_id': s.product_id,
                'product_name': s.product.name if s.product else f"Product #{s.product_id}",
                'category': s.product.category if s.product else "General",
                'quantity': s.quantity,
                'unit_price': s.unit_price,
                'total_amount': s.total_amount,
                'payment_method': s.payment_method,
                'is_refund': s.is_refund,
                'customer_name': s.customer.name if s.customer else None,
                'sold_at': s.sold_at.isoformat() if s.sold_at else '',
            }
            for s in rows
        ],
    }


def get_categories(db: Session) -> list:
    rows = (
        db.query(
            Product.category,
            func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
            func.coalesce(func.sum(Sale.quantity), 0).label('units'),
        )
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.is_refund.is_(False))
        .group_by(Product.category)
        .order_by(func.sum(Sale.total_amount).desc())
        .all()
    )
    return [
        {'category': r[0], 'revenue': round(float(r[1] or 0), 2), 'units': int(r[2] or 0)}
        for r in rows
    ]


def get_top_products(db: Session, limit: int = 5) -> list:
    rows = (
        db.query(
            Product.id,
            Product.name,
            Product.sku,
            Product.category,
            func.coalesce(func.sum(Sale.quantity), 0).label('units'),
            func.coalesce(func.sum(Sale.total_amount), 0).label('revenue'),
        )
        .join(Sale, Sale.product_id == Product.id)
        .filter(Sale.is_refund.is_(False))
        .group_by(Product.id, Product.name, Product.sku, Product.category)
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'product_id': r[0],
            'name': r[1],
            'sku': r[2],
            'category': r[3],
            'units': int(r[4] or 0),
            'revenue': round(float(r[5] or 0), 2),
        }
        for r in rows
    ]


def list_sales(db: Session, limit: int = 50, offset: int = 0) -> dict:
    q = db.query(Sale).order_by(Sale.sold_at.desc())
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        'total': total,
        'items': [
            {
                'id': s.id,
                'bill_number': s.bill_number,
                'product_id': s.product_id,
                'product_name': s.product.name if s.product else f"Product #{s.product_id}",
                'category': s.product.category if s.product else "General",
                'quantity': s.quantity,
                'unit_price': s.unit_price,
                'total_amount': s.total_amount,
                'payment_method': s.payment_method,
                'is_refund': s.is_refund,
                'customer_name': s.customer.name if s.customer else None,
                'sold_at': s.sold_at.isoformat() if s.sold_at else '',
            }
            for s in rows
        ],
    }


def get_revenue(db: Session, range_key: str = '7d') -> dict:
    return get_revenue_series(db, range_key)


def get_sales_performance(
    db: Session,
    range_key: str = '7d',
    start_date: str | None = None,
    end_date: str | None = None,
    product_id: int | None = None,
) -> dict:
    latest_sale = db.query(func.max(Sale.sold_at)).scalar()
    if latest_sale:
        if hasattr(latest_sale, 'date'):
            anchor = latest_sale.date()
        else:
            anchor = datetime.datetime.fromisoformat(str(latest_sale)[:19]).date()
    else:
        anchor = datetime.datetime.now(datetime.timezone.utc).date()

    earliest_sale = db.query(func.min(Sale.sold_at)).scalar()
    if earliest_sale:
        if hasattr(earliest_sale, 'date'):
            dataset_min = earliest_sale.date()
        else:
            dataset_min = datetime.datetime.fromisoformat(str(earliest_sale)[:19]).date()
    else:
        dataset_min = anchor

    # Determine date bounds for current and previous comparison periods
    if range_key == 'today':
        c_start = anchor
        c_end = anchor
        p_end = anchor - datetime.timedelta(days=1)
        p_start = p_end
        period_label = anchor.strftime('%d %b %Y')
        comp_label = p_start.strftime('%d %b %Y')
    elif range_key == '30d':
        c_end = anchor
        c_start = anchor - datetime.timedelta(days=29)
        p_end = c_start - datetime.timedelta(days=1)
        p_start = p_end - datetime.timedelta(days=29)
        period_label = f"{c_start.strftime('%d %b %Y')} – {c_end.strftime('%d %b %Y')}"
        comp_label = f"{p_start.strftime('%d %b %Y')} – {p_end.strftime('%d %b %Y')}"
    elif range_key == 'custom' and start_date and end_date:
        try:
            c_start = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
            c_end = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
            duration = max((c_end - c_start).days, 0)
            p_end = c_start - datetime.timedelta(days=1)
            p_start = p_end - datetime.timedelta(days=duration)
            period_label = f"{c_start.strftime('%d %b %Y')} – {c_end.strftime('%d %b %Y')}"
            comp_label = f"{p_start.strftime('%d %b %Y')} – {p_end.strftime('%d %b %Y')}"
        except Exception:
            c_end = anchor
            c_start = anchor - datetime.timedelta(days=6)
            p_end = c_start - datetime.timedelta(days=1)
            p_start = p_end - datetime.timedelta(days=6)
            period_label = f"{c_start.strftime('%d %b %Y')} – {c_end.strftime('%d %b %Y')}"
            comp_label = f"{p_start.strftime('%d %b %Y')} – {p_end.strftime('%d %b %Y')}"
    else:  # default '7d'
        range_key = '7d'
        c_end = anchor
        c_start = anchor - datetime.timedelta(days=6)
        p_end = c_start - datetime.timedelta(days=1)
        p_start = p_end - datetime.timedelta(days=6)
        period_label = f"{c_start.strftime('%d %b %Y')} – {c_end.strftime('%d %b %Y')}"
        comp_label = f"{p_start.strftime('%d %b %Y')} – {p_end.strftime('%d %b %Y')}"

    c_start_dt = datetime.datetime.combine(c_start, datetime.time.min, tzinfo=datetime.timezone.utc)
    c_end_dt = datetime.datetime.combine(c_end, datetime.time.max, tzinfo=datetime.timezone.utc)
    p_start_dt = datetime.datetime.combine(p_start, datetime.time.min, tzinfo=datetime.timezone.utc)
    p_end_dt = datetime.datetime.combine(p_end, datetime.time.max, tzinfo=datetime.timezone.utc)

    # Current period sales
    cq = db.query(Sale).filter(Sale.sold_at >= c_start_dt, Sale.sold_at <= c_end_dt, Sale.is_refund.is_(False))
    if product_id:
        cq = cq.filter(Sale.product_id == product_id)
    c_sales = cq.all()

    # Previous period sales
    pq = db.query(Sale).filter(Sale.sold_at >= p_start_dt, Sale.sold_at <= p_end_dt, Sale.is_refund.is_(False))
    if product_id:
        pq = pq.filter(Sale.product_id == product_id)
    p_sales = pq.all()

    total_revenue = round(sum(s.total_amount for s in c_sales), 2)
    units_sold = sum(s.quantity for s in c_sales)
    transactions = len({s.bill_number for s in c_sales})
    average_bill = round(total_revenue / transactions, 2) if transactions else 0.0

    prev_revenue = round(sum(s.total_amount for s in p_sales), 2)
    prev_units = sum(s.quantity for s in p_sales)
    prev_transactions = len({s.bill_number for s in p_sales})
    prev_avg_bill = round(prev_revenue / prev_transactions, 2) if prev_transactions else 0.0

    def pct_change(cur, prev):
        if prev is not None and prev > 0:
            return round(((cur - prev) / prev) * 100, 1)
        return None

    revenue_trend = pct_change(total_revenue, prev_revenue)
    units_trend = pct_change(units_sold, prev_units)
    trans_trend = pct_change(transactions, prev_transactions)
    avg_bill_trend = pct_change(average_bill, prev_avg_bill)

    # Build sales chart points
    sales_chart = []
    if range_key == 'today':
        hourly = {h: {'revenue': 0.0, 'units': 0, 'orders': set()} for h in range(8, 22)}
        for s in c_sales:
            h = s.sold_at.hour if hasattr(s.sold_at, 'hour') else 12
            if h in hourly:
                hourly[h]['revenue'] += s.total_amount
                hourly[h]['units'] += s.quantity
                hourly[h]['orders'].add(s.bill_number)
        for h in range(8, 22):
            sales_chart.append({
                'date': f"{c_start.strftime('%Y-%m-%d')}T{h:02d}:00:00",
                'label': f"{h:02d}:00",
                'revenue': round(hourly[h]['revenue'], 2),
                'units': hourly[h]['units'],
                'orders': len(hourly[h]['orders']),
            })
    else:
        daily = {}
        curr_d = c_start
        while curr_d <= c_end:
            daily[curr_d.strftime('%Y-%m-%d')] = {
                'label': curr_d.strftime('%d %b'),
                'revenue': 0.0,
                'units': 0,
                'orders': set(),
            }
            curr_d += datetime.timedelta(days=1)

        for s in c_sales:
            s_date = s.sold_at.date() if hasattr(s.sold_at, 'date') else str(s.sold_at)[:10]
            s_key = s_date if isinstance(s_date, str) else s_date.strftime('%Y-%m-%d')
            if s_key in daily:
                daily[s_key]['revenue'] += s.total_amount
                daily[s_key]['units'] += s.quantity
                daily[s_key]['orders'].add(s.bill_number)

        for k, v in sorted(daily.items()):
            sales_chart.append({
                'date': k,
                'label': v['label'],
                'revenue': round(v['revenue'], 2),
                'units': v['units'],
                'orders': len(v['orders']),
            })

    # Product Sales Performance
    prod_map = {}
    for s in c_sales:
        pid = s.product_id
        if pid not in prod_map:
            pname = s.product.name if s.product else f"Product #{pid}"
            sku = s.product.sku if s.product else f"SKU-{pid}"
            cat = s.product.category if s.product else "General"
            prod_map[pid] = {
                'product_id': pid,
                'name': pname,
                'sku': sku,
                'category': cat,
                'units_sold': 0,
                'revenue': 0.0,
                'prev_units': 0,
            }
        prod_map[pid]['units_sold'] += s.quantity
        prod_map[pid]['revenue'] += s.total_amount

    # Map previous units for trend
    for s in p_sales:
        if s.product_id in prod_map:
            prod_map[s.product_id]['prev_units'] += s.quantity

    prod_list = list(prod_map.values())
    prod_list.sort(key=lambda x: x['revenue'], reverse=True)

    total_prods = len(prod_list)
    for idx, p in enumerate(prod_list):
        p['revenue'] = round(p['revenue'], 2)
        p['avg_price'] = round(p['revenue'] / max(p['units_sold'], 1), 2)
        p['sales_trend'] = pct_change(p['units_sold'], p['prev_units'])
        if idx < total_prods * 0.25:
            p['performance'] = 'Top Seller'
        elif idx < total_prods * 0.5:
            p['performance'] = 'High Demand'
        elif idx < total_prods * 0.75:
            p['performance'] = 'Moderate'
        else:
            p['performance'] = 'Low Demand'

    # Daily breakdown table rows
    daily_breakdown = []
    if range_key != 'today':
        for pt in sales_chart:
            daily_breakdown.append({
                'date': pt['date'],
                'label': pt['label'],
                'units_sold': pt['units'],
                'revenue': pt['revenue'],
                'transactions': pt['orders'],
                'average_bill': round(pt['revenue'] / max(pt['orders'], 1), 2) if pt['orders'] else 0.0,
            })
        daily_breakdown.sort(key=lambda x: x['date'], reverse=True)
    else:
        daily_breakdown = [{
            'date': c_start.strftime('%Y-%m-%d'),
            'label': c_start.strftime('%d %b %Y'),
            'units_sold': units_sold,
            'revenue': total_revenue,
            'transactions': transactions,
            'average_bill': average_bill,
        }]

    # Calculated Sales Intelligence
    insights = []
    if total_revenue > 0:
        if revenue_trend is not None:
            dir_str = "increased" if revenue_trend >= 0 else "decreased"
            insights.append({
                'title': 'Revenue Trajectory',
                'insight': f"Revenue {dir_str} by {abs(revenue_trend)}% compared to the prior period (₹{total_revenue:,.2f} vs ₹{prev_revenue:,.2f}).",
                'type': 'growth' if revenue_trend >= 0 else 'warning',
            })
        else:
            insights.append({
                'title': 'Revenue Trajectory',
                'insight': f"Total revenue generated reached ₹{total_revenue:,.2f} across {transactions} transactions.",
                'type': 'info',
            })

        if prod_list:
            top_rev = prod_list[0]
            insights.append({
                'title': 'Top Revenue Generator',
                'insight': f"{top_rev['name']} led the catalog with ₹{top_rev['revenue']:,.2f} in revenue ({top_rev['units_sold']} units).",
                'type': 'star',
            })
            top_vol = max(prod_list, key=lambda x: x['units_sold'])
            insights.append({
                'title': 'Peak Sales Volume',
                'insight': f"{top_vol['name']} achieved the highest unit throughput at {top_vol['units_sold']} units sold.",
                'type': 'volume',
            })

        if sales_chart:
            peak_day = max(sales_chart, key=lambda x: x['revenue'])
            if peak_day['revenue'] > 0:
                insights.append({
                    'title': 'Highest Sales Period',
                    'insight': f"Peak velocity was recorded on {peak_day['label']} with ₹{peak_day['revenue']:,.2f} from {peak_day['orders']} orders.",
                    'type': 'timing',
                })

        avg_basket_units = round(units_sold / max(transactions, 1), 1)
        insights.append({
            'title': 'Checkout Efficiency',
            'insight': f"Average transaction value stood at ₹{average_bill:,.2f} with an average of {avg_basket_units} items per checkout.",
            'type': 'basket',
        })
    else:
        insights.append({
            'title': 'Sales Intelligence',
            'insight': 'No sales transactions recorded for this filter selection.',
            'type': 'empty',
        })

    # CCTV Foot Traffic Correlation
    cctv_correlation = {
        'available': False,
        'message': 'CCTV analytics unavailable for the selected period.',
        'cam1_traffic': None,
        'cam2_traffic': None,
        'combined_traffic': None,
        'sales_revenue': total_revenue,
        'conversion_rate': None,
        'relationship_note': 'Synchronized camera telemetry requires active in-store CCTV stream. Real-time vision is active on /monitoring.',
    }

    try:
        from app.routers import store_monitor as sm
        j1 = sm._get_job('camera_01')
        j2 = sm._get_job('camera_02')
        if (j1 and j1.state == 'ready') or (j2 and j2.state == 'ready'):
            t1 = len(getattr(j1, 'lifecycles', {}) or {}) if j1 else 0
            t2 = len(getattr(j2, 'lifecycles', {}) or {}) if j2 else 0
            comb = t1 + t2
            cctv_correlation['available'] = True
            cctv_correlation['message'] = None
            cctv_correlation['cam1_traffic'] = t1
            cctv_correlation['cam2_traffic'] = t2
            cctv_correlation['combined_traffic'] = comb
            if comb > 0 and transactions > 0:
                cctv_correlation['relationship_note'] = f"Active camera coverage recorded {comb} customer track sessions during dual-camera monitoring."
            else:
                cctv_correlation['relationship_note'] = f"Dual-camera monitoring tracking active ({comb} customer detections observed)."
    except Exception:
        pass

    # Payment Intelligence & Recent Transactions
    pay_counts = {}
    pay_revenues = {}
    for s in c_sales:
        pm = s.payment_method or 'UPI'
        pay_counts[pm] = pay_counts.get(pm, 0) + 1
        pay_revenues[pm] = pay_revenues.get(pm, 0.0) + s.total_amount

    total_txns = len(c_sales)
    method_order = ['UPI', 'Cash', 'Credit Card', 'Debit Card']
    all_methods = sorted(
        pay_counts.keys(),
        key=lambda m: (method_order.index(m) if m in method_order else 99, -pay_counts[m])
    )

    payment_distribution = []
    for m in all_methods:
        c = pay_counts[m]
        rev = round(pay_revenues[m], 2)
        pct = round((c / total_txns) * 100, 1) if total_txns else 0.0
        rev_pct = round((rev / total_revenue) * 100, 1) if total_revenue else 0.0
        payment_distribution.append({
            'method': m,
            'count': c,
            'amount': rev,
            'percentage': pct,
            'revenue_percentage': rev_pct,
        })

    top_pm = payment_distribution[0]['method'] if payment_distribution else 'UPI'
    cash_share = round((pay_counts.get('Cash', 0) / total_txns) * 100, 1) if total_txns else 0.0
    card_count = pay_counts.get('Credit Card', 0) + pay_counts.get('Debit Card', 0)
    card_share = round((card_count / total_txns) * 100, 1) if total_txns else 0.0
    upi_share = round((pay_counts.get('UPI', 0) / total_txns) * 100, 1) if total_txns else 0.0

    pay_insights = []
    if total_txns > 0:
        if upi_share >= 35:
            pay_insights.append(f"UPI is the primary checkout channel, driving {upi_share}% of all customer transactions.")
        elif top_pm:
            pay_insights.append(f"{top_pm} is the most frequently used payment method for this period.")

        card_rev = pay_revenues.get('Credit Card', 0.0) + pay_revenues.get('Debit Card', 0.0)
        cash_rev = pay_revenues.get('Cash', 0.0)
        card_avg = round(card_rev / card_count, 2) if card_count else 0.0
        cash_avg = round(cash_rev / pay_counts.get('Cash', 1), 2) if pay_counts.get('Cash', 0) else 0.0

        if card_avg > cash_avg and card_avg > 0:
            pay_insights.append(f"Card transactions average ₹{card_avg:,.2f}, representing higher checkout ticket sizes than cash (₹{cash_avg:,.2f}).")
        elif cash_share > 0:
            pay_insights.append(f"Cash accounts for {cash_share}% of total counter checkouts.")

        if card_share > 0:
            pay_insights.append(f"Combined digital card payments (Credit & Debit) represent {card_share}% of transaction volume.")
    else:
        pay_insights.append("No payment transactions recorded for the selected period.")

    # Recent transactions sorted descending by timestamp
    sorted_sales = sorted(
        c_sales,
        key=lambda s: (s.sold_at.isoformat() if hasattr(s.sold_at, 'isoformat') else str(s.sold_at)) if s.sold_at else '',
        reverse=True
    )
    recent_transactions = []
    for s in sorted_sales[:60]:
        time_str = s.sold_at.strftime('%H:%M') if hasattr(s.sold_at, 'strftime') else '--:--'
        date_str = s.sold_at.strftime('%Y-%m-%d') if hasattr(s.sold_at, 'strftime') else str(s.sold_at)[:10]
        raw_b = s.bill_number or f"BILL-{s.id:05d}"
        parts = raw_b.split('-')
        disp_id = f"TXN-{parts[-1]}" if len(parts) > 1 else f"TXN-{s.id:05d}"
        recent_transactions.append({
            'id': s.id,
            'bill_number': raw_b,
            'display_id': disp_id,
            'date': date_str,
            'time': time_str,
            'timestamp': s.sold_at.isoformat() if hasattr(s.sold_at, 'isoformat') else str(s.sold_at),
            'amount': round(s.total_amount, 2),
            'payment_method': s.payment_method or 'UPI',
            'product_name': s.product.name if s.product else (f"Product #{s.product_id}" if s.product_id else "Retail Item"),
            'quantity': s.quantity,
        })

    return {
        'data_period': {
            'anchor_date': anchor.strftime('%Y-%m-%d'),
            'dataset_min': dataset_min.strftime('%Y-%m-%d'),
            'period_label': period_label,
            'comparison_label': comp_label,
            'range_key': range_key,
            'start_date': c_start.strftime('%Y-%m-%d'),
            'end_date': c_end.strftime('%Y-%m-%d'),
        },
        'kpis': {
            'total_revenue': total_revenue,
            'transactions': transactions,
            'units_sold': units_sold,
            'average_bill': average_bill,
            'trends': {
                'revenue_change_pct': revenue_trend,
                'units_change_pct': units_trend,
                'transactions_change_pct': trans_trend,
                'avg_bill_change_pct': avg_bill_trend,
                'comparison_period_label': comp_label,
            },
        },
        'sales_chart': sales_chart,
        'sales_intelligence': {
            'source': 'CALCULATED FROM SALES DATA',
            'items': insights,
        },
        'product_performance': prod_list,
        'daily_breakdown': daily_breakdown,
        'cctv_correlation': cctv_correlation,
        'payment_intelligence': {
            'source': 'REAL SALES DATA WITH PROTOTYPE CLASSIFICATION',
            'distribution': payment_distribution,
            'summary': {
                'total_transactions': transactions,
                'total_sales': total_revenue,
                'average_transaction': average_bill,
                'top_payment_method': top_pm,
                'cash_share_pct': cash_share,
                'card_share_pct': card_share,
                'upi_share_pct': upi_share,
            },
            'insights': pay_insights,
            'recent_transactions': recent_transactions,
        },
    }


def import_sales_records(db: Session, records: list[dict]) -> dict:
    """Import bulk billing & sales records into database."""
    imported_count = 0
    total_imported_revenue = 0.0
    products = db.query(Product).all()
    sku_to_id = {p.sku.upper(): p.id for p in products if p.sku}
    name_to_id = {p.name.lower(): p.id for p in products if p.name}
    default_product_id = products[0].id if products else 1

    for rec in records:
        sku = str(rec.get('product_sku') or rec.get('sku') or '').strip().upper()
        name = str(rec.get('product_name') or rec.get('name') or '').strip().lower()

        prod_id = sku_to_id.get(sku) or name_to_id.get(name) or default_product_id

        bill_num = str(
            rec.get('bill_number')
            or rec.get('invoice_number')
            or rec.get('invoice_no')
            or rec.get('bill_no')
            or f"INV-IMP-{imported_count+1001}"
        )
        qty = int(rec.get('quantity') or rec.get('qty') or rec.get('units_sold') or 1)
        price = float(rec.get('unit_price') or rec.get('price') or rec.get('rate') or 0.0)
        tot = float(rec.get('total_amount') or rec.get('amount') or rec.get('revenue') or (qty * price))
        pay_method = str(rec.get('payment_method') or rec.get('payment_mode') or 'UPI')

        sold_at_str = rec.get('sold_at') or rec.get('date') or rec.get('bill_date')
        sold_at = datetime.datetime.now(datetime.timezone.utc)
        if sold_at_str:
            try:
                sold_at = datetime.datetime.fromisoformat(str(sold_at_str).replace('Z', '+00:00'))
            except Exception:
                pass

        sale_entry = Sale(
            bill_number=bill_num,
            product_id=prod_id,
            quantity=qty,
            unit_price=price,
            total_amount=tot,
            payment_method=pay_method,
            is_refund=bool(rec.get('is_refund', False)),
            sold_at=sold_at,
        )
        db.add(sale_entry)
        imported_count += 1
        total_imported_revenue += tot

    db.commit()
    return {
        'status': 'success',
        'imported_count': imported_count,
        'total_revenue': round(total_imported_revenue, 2),
        'message': f'Successfully imported {imported_count} billing & sales records.',
    }

