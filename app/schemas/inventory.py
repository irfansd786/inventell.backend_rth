from pydantic import BaseModel


class InventoryOut(BaseModel):
    id: int
    product_id: int
    name: str = ''
    sku: str = ''
    store_stock: int = 0
    warehouse_stock: int = 0
    reserved_stock: int = 0
    reorder_level: int = 0
    status: str = 'Healthy'
    available_stock: int = 0


class ReplenishIn(BaseModel):
    product_id: int
    quantity: int
    source: str = 'warehouse'
