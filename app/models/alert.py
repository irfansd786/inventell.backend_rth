import datetime
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    __tablename__ = 'alerts'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(250))
    message: Mapped[str] = mapped_column(Text, default='')
    category: Mapped[str] = mapped_column(String(100), default='general')
    severity: Mapped[str] = mapped_column(String(20), default='LOW')
    link: Mapped[str] = mapped_column(String(150), default='/alerts')
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        index=True,
    )
