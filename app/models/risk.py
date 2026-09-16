import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Risk(Base):
    __tablename__ = 'risks'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)  # CRITICAL | HIGH | MEDIUM | LOW
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default='')
    category: Mapped[str] = mapped_column(String(100), default='inventory')
    product_id: Mapped[int | None] = mapped_column(ForeignKey('products.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='active', index=True)
    action_label: Mapped[str] = mapped_column(String(100), default='Review')
    action_path: Mapped[str] = mapped_column(String(100), default='/risks')
    meta_json: Mapped[str] = mapped_column(Text, default='{}')
    score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
    )
