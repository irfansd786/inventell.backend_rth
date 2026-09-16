from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Customer(Base):
    __tablename__ = 'customers'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    segment: Mapped[str] = mapped_column(String(50), default='walk-in')

    sales: Mapped[list['Sale']] = relationship(back_populates='customer')
    orders: Mapped[list['Order']] = relationship(back_populates='customer')
