from pydantic import BaseModel


class SalesSummary(BaseModel):
    revenue: float = 0
    orders: int = 0
    units_sold: int = 0
    average_order_value: float = 0
    refunds: float = 0
    net_revenue: float = 0


class CategorySales(BaseModel):
    category: str
    revenue: float = 0
    units: int = 0


class TopProduct(BaseModel):
    product_id: int
    name: str
    sku: str
    units: int = 0
    revenue: float = 0


class SaleOut(BaseModel):
    id: int
    bill_number: str
    product_id: int
    quantity: int
    unit_price: float
    total_amount: float
    payment_method: str
    is_refund: bool = False
    sold_at: str = ''

    model_config = {'from_attributes': True}
