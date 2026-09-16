from pydantic import BaseModel


class DashboardSummary(BaseModel):
    revenue_today: float = 0
    orders_today: int = 0
    customers_today: int = 0
    transactions_today: int = 0
    products_sold: int = 0
    average_order_value: float = 0
    conversion_rate: float = 0
    inventory_value: float = 0
    low_stock_count: int = 0
    critical_risk_count: int = 0
    revenue_change_pct: float = 0
    orders_change_pct: float = 0
    customers_change_pct: float = 0


class RevenuePoint(BaseModel):
    label: str
    revenue: float = 0
    orders: int = 0


class RevenueSeries(BaseModel):
    current: float = 0
    previous: float = 0
    change_pct: float = 0
    points: list[RevenuePoint] = []


class StoreIntelligence(BaseModel):
    customers_current: int = 0
    customers_today: int = 0
    average_dwell_time: str = '—'
    peak_hour: str = '—'
    queue_length: int = 0
    busiest_zone: str = '—'


class InventoryItemOut(BaseModel):
    product_id: int
    name: str
    sku: str
    store_stock: int = 0
    reorder_level: int = 0
    warehouse_stock: int = 0
    status: str = 'Healthy'


class InventoryHealth(BaseModel):
    healthy: int = 0
    low_stock: int = 0
    critical: int = 0
    out_of_stock: int = 0
    inventory_value: float = 0
    store_stock: int = 0
    warehouse_stock: int = 0
    reserved_stock: int = 0
    items: list[InventoryItemOut] = []


class RiskOut(BaseModel):
    id: int
    severity: str
    title: str
    description: str = ''
    category: str = ''
    status: str = 'active'
    action_label: str = 'Review'
    action_path: str = '/risks'
    created_at: str = ''

    model_config = {'from_attributes': True}


class InsightOut(BaseModel):
    id: int | str
    type: str
    title: str
    explanation: str = ''
    confidence: int = 0
    action: str = ''
    action_path: str = ''


class OperationsFlow(BaseModel):
    orders_pending: int = 0
    allocated: int = 0
    picking: int = 0
    packing: int = 0
    ready_for_dispatch: int = 0
    dispatched: int = 0
