"""Notifications to the marketer (specs/012 data-model.md › Model `Notification`). Mirrors 0015.

Holds no subscriber name, phone, numbers, address or note (FR-019); `reason` is a code from a
fixed list, shown by its label.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

NOTIFICATION_KINDS = ("approved", "rejected", "linked", "unlinked", "deleted")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('approved','rejected','linked','unlinked','deleted')",
            name="notifications_kind",
        ),
        CheckConstraint(
            "(kind NOT IN ('approved','linked') OR reason IS NULL) "
            "AND (kind NOT IN ('rejected','deleted','unlinked') OR reason IS NOT NULL)",
            name="notifications_reason_kind",
        ),
        Index(
            "notifications_once",
            "request_id",
            "kind",
            unique=True,
            postgresql_where=text("kind IN ('approved','rejected','deleted')"),
        ),
        Index("notifications_marketer_id", "marketer_id", text("id DESC")),
        Index("notifications_unread", "marketer_id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    marketer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("requests.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    request = relationship("Request", lazy="joined")
