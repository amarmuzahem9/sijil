"""Requests exports (specs/019 data-model.md › exports).

One row per «تصدير» of «التقارير والتصدير». The row holds ids, codes and counts only, never
subscriber data; the file itself is in EXPORTS_DIR/<id>/ and is removed 24 h after it is ready
(research R10).
Only the requester may see, ticket or download an export (FR-012).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now
from app.models.base import Base

EXPORT_STATES: tuple[str, ...] = ("preparing", "ready", "failed", "removed")


class Export(Base):
    __tablename__ = "exports"
    __table_args__ = (
        CheckConstraint("state IN ('preparing','ready','failed','removed')", name="exports_state"),
        CheckConstraint(
            "(state = 'ready') = "
            "(ready_at IS NOT NULL AND expires_at IS NOT NULL AND removed_at IS NULL)",
            name="exports_ready_times",
        ),
        Index(
            "exports_one_preparing",
            "requester_id",
            unique=True,
            postgresql_where=text("state = 'preparing'"),
        ),
        Index("exports_requester_created", "requester_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # Ids and codes only (research R8): period, from, to, date_kind, area_id, tower_id,
    # marketer_id, plan_id, status, type.
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    include_identity: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    missing_images: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Text)
    # SHA-256 of the current one-use download ticket (research R7); cleared when used.
    ticket_hash: Mapped[str | None] = mapped_column(Text)
    ticket_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
