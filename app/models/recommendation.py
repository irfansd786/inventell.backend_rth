import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Recommendation(Base):
    """Inventory Risk Engine Recommendation model for automated workflow approvals."""

    __tablename__ = 'recommendations'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), index=True)
    recommendation_type: Mapped[str] = mapped_column(String(50), default='REPLENISHMENT', index=True)
    title: Mapped[str] = mapped_column(String(250))
    reason: Mapped[str] = mapped_column(Text, default='')
    discount_pct: Mapped[int] = mapped_column(Integer, default=0)
    suggested_qty: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[str] = mapped_column(String(20), default='HIGH', index=True)
    status: Mapped[str] = mapped_column(String(20), default='PENDING', index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    product: Mapped['Product'] = relationship()
