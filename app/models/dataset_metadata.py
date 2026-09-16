import datetime
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatasetMetadata(Base):
    __tablename__ = 'dataset_metadata'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(100), default='Kaggle')
    file_name: Mapped[str] = mapped_column(String(255))
    date_range: Mapped[str] = mapped_column(String(100))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default='Connected')  # 'Connected', 'Not Connected', 'Historical'
    purpose: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default='')
    last_ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
