from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    cost_price: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(20), default='pcs')
    dataset_source: Mapped[str | None] = mapped_column(String(100), nullable=True, default='M5')
    is_active: Mapped[bool] = mapped_column(default=True)

    inventory: Mapped[list['Inventory']] = relationship(back_populates='product', cascade='all, delete-orphan')
    sales: Mapped[list['Sale']] = relationship(back_populates='product')
    order_items: Mapped[list['OrderItem']] = relationship(back_populates='product')
