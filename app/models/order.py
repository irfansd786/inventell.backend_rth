import datetime
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# PENDING → ALLOCATED → PICKING → PACKING → READY → DISPATCHED
ORDER_STATUSES = ('PENDING', 'ALLOCATED', 'PICKING', 'PACKING', 'READY', 'DISPATCHED', 'CANCELLED')

ALLOWED_TRANSITIONS = {
    'PENDING': ('ALLOCATED', 'CANCELLED'),
    'ALLOCATED': ('PICKING', 'CANCELLED'),
    'PICKING': ('PACKING', 'CANCELLED'),
    'PACKING': ('READY', 'CANCELLED'),
    'READY': ('DISPATCHED',),
    'DISPATCHED': tuple(),
    'CANCELLED': tuple(),
}


class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey('customers.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='PENDING', index=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    customer: Mapped['Customer | None'] = relationship(back_populates='orders')
    items: Mapped[list['OrderItem']] = relationship(back_populates='order', cascade='all, delete-orphan')
