import datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DemandForecast(Base):
    __tablename__ = 'demand_forecasts'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey('products.id'), nullable=True, index=True)
    item_sku: Mapped[str] = mapped_column(String(100), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    store_id: Mapped[str] = mapped_column(String(50), default='CA_1', index=True)
    forecast_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    predicted_demand: Mapped[float] = mapped_column(Float, default=0.0)
    actual_demand: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower_bound: Mapped[float] = mapped_column(Float, default=0.0)
    upper_bound: Mapped[float] = mapped_column(Float, default=0.0)
    model_name: Mapped[str] = mapped_column(String(100), default='Ridge Regression / Rolling Baseline')
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    product: Mapped['Product | None'] = relationship()


class ForecastMetric(Base):
    __tablename__ = 'forecast_metrics'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    rmse: Mapped[float] = mapped_column(Float, default=0.0)
    mape: Mapped[float] = mapped_column(Float, default=0.0)
    r2_score: Mapped[float] = mapped_column(Float, default=0.0)
    training_sample_size: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
