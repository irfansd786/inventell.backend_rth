from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Inventory(Base):
    """Per-product stock split between the store and the warehouse."""

    __tablename__ = 'inventory'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), unique=True, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey('warehouses.id'), nullable=True)
    store_stock: Mapped[int] = mapped_column(Integer, default=0)
    warehouse_stock: Mapped[int] = mapped_column(Integer, default=0)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(20), default='Healthy')

    product: Mapped['Product'] = relationship(back_populates='inventory')
    warehouse: Mapped['Warehouse | None'] = relationship(back_populates='inventory_lines')

    @property
    def available_stock(self) -> int:
        return (self.store_stock or 0) + (self.warehouse_stock or 0) - (self.reserved_stock or 0)
