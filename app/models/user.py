import datetime
import json
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), default='User')
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True, default='')
    role: Mapped[str] = mapped_column(String(20), default='employee')  # 'admin' | 'employee' | legacy 'ADMIN' | 'MANAGER' | 'STAFF'
    status: Mapped[str] = mapped_column(String(20), default='active')  # 'active' | 'inactive'
    assigned_modules: Mapped[str] = mapped_column(Text, default='[]')  # JSON array string
    store: Mapped[str] = mapped_column(String(120), default='Main Street Store')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    last_login: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    activity_logs: Mapped[list['ActivityLog']] = relationship(back_populates='user')

    @property
    def is_admin(self) -> bool:
        r = (self.role or '').lower()
        return r in ('admin', 'manager')

    @property
    def permissions(self) -> list[str]:
        if self.is_admin:
            from app.core.permissions import ALL_PERMISSIONS
            return list(ALL_PERMISSIONS)
        try:
            return json.loads(self.assigned_modules or '[]')
        except Exception:
            return []

    def has_permission(self, perm: str) -> bool:
        if self.is_admin:
            return True
        if not self.is_active or self.status == 'inactive':
            return False
        return perm in self.permissions

    def to_profile_dict(self) -> dict:
        return {
            'uid': self.firebase_uid or f"usr_{self.id}",
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': 'admin' if self.is_admin else 'employee',
            'status': 'inactive' if (not self.is_active or self.status == 'inactive') else 'active',
            'assigned_modules': self.permissions,
            'store': self.store,
            'created_at': self.created_at.isoformat() if self.created_at else '',
            'last_login': self.last_login.isoformat() if self.last_login else '',
        }
