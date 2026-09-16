from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_sales_performance_endpoint():
    res = client.get('/api/sales/performance?range=7d')
    assert res.status_code == 200
    data = res.json()
    assert 'kpis' in data
    assert 'total_revenue' in data['kpis']
    assert 'transactions' in data['kpis']
    assert 'units_sold' in data['kpis']
    assert 'average_bill' in data['kpis']
    assert 'sales_chart' in data
    assert len(data['sales_chart']) == 7
    assert 'sales_intelligence' in data
    assert 'product_performance' in data
    assert 'daily_breakdown' in data
    assert 'cctv_correlation' in data
    assert 'payment_intelligence' in data
    assert 'distribution' in data['payment_intelligence']
    assert 'summary' in data['payment_intelligence']
    assert 'recent_transactions' in data['payment_intelligence']


def test_sales_performance_today():
    res = client.get('/api/sales/performance?range=today')
    assert res.status_code == 200
    data = res.json()
    assert data['data_period']['range_key'] == 'today'
    assert len(data['sales_chart']) > 0


def test_products_catalog_endpoint():
    res = client.get('/api/products/catalog')
    assert res.status_code == 200
    products = res.json()
    assert isinstance(products, list)
    assert len(products) > 0
    p = products[0]
    assert 'sku' in p
    assert 'name' in p
    assert 'price' in p
    assert 'store_stock' in p
    assert 'warehouse_stock' in p
    assert 'total_stock' in p
    assert 'stock_status' in p
    assert 'barcode' in p
    assert p['barcode'] is None  # Truthful to dataset


def test_products_summary_endpoint():
    res = client.get('/api/products/summary')
    assert res.status_code == 200
    data = res.json()
    assert 'total_products' in data
    assert 'active_products' in data
    assert 'total_skus' in data
    assert 'total_units' in data
    assert data['total_products'] > 0


def test_products_kpis_endpoint():
    res = client.get('/api/products/kpis')
    assert res.status_code == 200
    kpis = res.json()
    assert 'total_products' in kpis
    assert 'active_products' in kpis
    assert 'low_stock' in kpis
    assert 'top_seller' in kpis


def test_product_details_endpoint():
    # First get catalog to pick a real product id
    cat_res = client.get('/api/products/catalog')
    products = cat_res.json()
    pid = products[0]['id']

    res = client.get(f'/api/products/{pid}/details')
    assert res.status_code == 200
    detail = res.json()
    assert detail['id'] == pid
    assert 'sales_trend' in detail
    assert 'customer_activity' in detail
    assert detail['barcode'] is None


def test_inventory_list_endpoint():
    res = client.get('/api/inventory')
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) > 0
    first = items[0]
    assert 'product_id' in first
    assert 'name' in first
    assert 'sku' in first
    assert 'category' in first
    assert 'price' in first
    assert 'store_stock' in first
    assert 'warehouse_stock' in first
    assert 'total_stock' in first
    assert 'reorder_level' in first
    assert 'status' in first
    assert 'units_sold' in first
    assert 'sales_velocity' in first
    assert 'barcode' in first


def test_inventory_summary_endpoint():
    res = client.get('/api/inventory/summary')
    assert res.status_code == 200
    s = res.json()
    assert 'total_products' in s
    assert 'total_units' in s
    assert 'inventory_value' in s
    assert 'healthy' in s
    assert 'low_stock' in s
    assert 'critical' in s
    assert 'out_of_stock' in s
    assert 'categories' in s


def test_inventory_low_stock_endpoint():
    res = client.get('/api/inventory/low-stock')
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    for it in items:
        assert 'days_of_stock' in it
        assert 'demand_risk' in it
        assert 'recommended_replenishment' in it
        assert 'severity' in it


def test_forecast_demand_endpoint():
    res = client.get('/api/forecast/demand')
    assert res.status_code == 200
    data = res.json()
    assert 'kpis' in data
    assert 'productsForecasted' in data['kpis']
    assert 'demandOpportunities' in data['kpis']
    assert 'replenishmentRequired' in data['kpis']
    assert 'chart' in data
    assert len(data['chart']) > 0
    assert 'products' in data
    assert len(data['products']) > 0
    assert 'events' in data
    assert len(data['events']) > 0
    assert 'products_to_watch' in data
    assert 'active_event' in data
    assert 'category_forecast' in data
    assert 'seasonal_insights' in data
    assert 'inventory_preparation' in data
    assert 'ai_summary' in data
    assert 'cctv_correlation' in data


def test_forecast_events_endpoint():
    res = client.get('/api/forecast/events')
    assert res.status_code == 200
    events = res.json()
    assert isinstance(events, list)
    assert len(events) >= 6
    names = [e['name'] for e in events]
    assert 'Vinayaka Chaturthi' in names
    assert 'Dussehra' in names
    assert 'Diwali' in names


def test_forecast_event_filter():
    res = client.get('/api/forecast/demand?event_id=vinayaka-chaturthi&period_days=14')
    assert res.status_code == 200
    data = res.json()
    assert data['active_event']['id'] == 'vinayaka-chaturthi'
    assert data['active_event']['days_away'] == 5
    assert len(data['products_to_watch']) > 0


