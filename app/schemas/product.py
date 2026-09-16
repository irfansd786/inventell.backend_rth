from pydantic import BaseModel


class ProductIn(BaseModel):
    sku: str
    name: str
    category: str = 'Grocery'
    price: float = 0
    cost_price: float = 0
    unit: str = 'pcs'


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    price: float | None = None
    cost_price: float | None = None
    unit: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    price: float
    cost_price: float
    unit: str
    is_active: bool

    model_config = {'from_attributes': True}
