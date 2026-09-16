from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Supplier(Base):
    __tablename__ = 'suppliers'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    contact: Mapped[str] = mapped_column(String(100), default='')
    phone: Mapped[str] = mapped_column(String(20), default='')
    category: Mapped[str] = mapped_column(String(100), default='')
    status: Mapped[str] = mapped_column(String(20), default='Active')
