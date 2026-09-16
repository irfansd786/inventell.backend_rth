from pydantic import BaseModel


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int
    unit_price: float | None = None


class OrderIn(BaseModel):
    customer_id: int | None = None
    items: list[OrderItemIn]


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float

    model_config = {'from_attributes': True}


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_id: int | None = None
    status: str
    total_amount: float
    items: list[OrderItemOut] = []

    model_config = {'from_attributes': True}


class OrderStatusIn(BaseModel):
    status: str
