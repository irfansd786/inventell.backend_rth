import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Transfer(Base):
    """Stock movement: Main Warehouse → Main Street Store (single-lane scope)."""

    __tablename__ = 'transfers'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transfer_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'))
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='PENDING', index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    warehouse: Mapped['Warehouse'] = relationship(back_populates='transfers_out', foreign_keys=[warehouse_id])
    product: Mapped['Product'] = relationship()
