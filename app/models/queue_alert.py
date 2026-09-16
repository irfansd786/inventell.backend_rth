import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QueueAlert(Base):
    __tablename__ = 'queue_alerts'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    camera_id: Mapped[str] = mapped_column(String(50), default='camera_01', index=True)
    queue_length: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[int] = mapped_column(Integer, default=6)
    average_wait_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    growth_rate: Mapped[str] = mapped_column(String(50), default='STABLE')
    duration_minutes: Mapped[int] = mapped_column(Integer, default=1)
    severity: Mapped[str] = mapped_column(String(20), default='HIGH', index=True)
    recommendation: Mapped[str] = mapped_column(String(255), default='Open an additional checkout counter')
    reason: Mapped[str] = mapped_column(Text, default='')
    priority: Mapped[str] = mapped_column(String(20), default='HIGH')
    status: Mapped[str] = mapped_column(String(50), default='Active', index=True)
    action_taken: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
