"""users — data-model.md › users. Rows are never deleted, only deactivated (Principle III)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now
from app.models.base import Base

ROLES = ("super_admin", "admin", "marketer")
ADMIN_PERMISSIONS = ("review", "link", "settings", "marketers", "reports", "commissions")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("phone ~ '^07[0-9]{9}$'", name="users_phone_format"),
        CheckConstraint("role IN ('super_admin', 'admin', 'marketer')", name="users_role_valid"),
        CheckConstraint("char_length(name) BETWEEN 2 AND 100", name="users_name_length"),
        CheckConstraint(
            "role = 'admin' OR permissions = '[]'::jsonb", name="users_permissions_admin_only"
        ),
        CheckConstraint("failed_logins >= 0", name="users_failed_logins_nonnegative"),
        Index("users_super_admin_idx", "role", postgresql_where=text("role = 'super_admin'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    failed_logins: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("now()"),
    )
