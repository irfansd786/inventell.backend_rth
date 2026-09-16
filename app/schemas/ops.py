from pydantic import BaseModel


class WarehouseOut(BaseModel):
    id: int
    code: str
    name: str
    location: str = ''
    capacity: int = 0

    model_config = {'from_attributes': True}


class TransferIn(BaseModel):
    product_id: int
    quantity: int
    warehouse_id: int | None = None


class TransferOut(BaseModel):
    id: int
    transfer_number: str
    warehouse_id: int
    product_id: int
    quantity: int
    status: str

    model_config = {'from_attributes': True}


class SupplierIn(BaseModel):
    name: str
    contact: str = ''
    phone: str = ''
    category: str = ''


class SupplierOut(BaseModel):
    id: int
    name: str
    contact: str = ''
    phone: str = ''
    category: str = ''
    status: str = 'Active'

    model_config = {'from_attributes': True}


class RiskCreate(BaseModel):
    severity: str
    title: str
    description: str = ''
    category: str = 'general'
    product_id: int | None = None


class RiskOut(BaseModel):
    id: int
    severity: str
    title: str
    description: str = ''
    category: str = ''
    status: str = 'active'

    model_config = {'from_attributes': True}


class AlertOut(BaseModel):
    id: int
    title: str
    message: str = ''
    category: str = ''
    severity: str = ''
    link: str = ''
    is_read: bool = False

    model_config = {'from_attributes': True}
