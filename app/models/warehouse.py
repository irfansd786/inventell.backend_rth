from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Warehouse(Base):
    __tablename__ = 'warehouses'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(200), default='')
    capacity: Mapped[int] = mapped_column(default=10000)

    inventory_lines: Mapped[list['Inventory']] = relationship(back_populates='warehouse')
    transfers_out: Mapped[list['Transfer']] = relationship(
        back_populates='warehouse', foreign_keys='Transfer.warehouse_id'
    )
