import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Sale(Base):
    __tablename__ = 'sales'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bill_number: Mapped[str] = mapped_column(String(50), index=True)
    store_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey('customers.id'), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(30), default='Credit Card')
    is_refund: Mapped[bool] = mapped_column(default=False)
    sold_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
    )

    product: Mapped['Product'] = relationship(back_populates='sales')
    customer: Mapped['Customer | None'] = relationship(back_populates='sales')
