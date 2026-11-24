"""Legacy subscribers from the old Google Form (specs/014 data-model.md). Mirrors migration 0017.

A legacy subscriber is not a request: no marketer, no status in the request flow, no username or
tower. Rows are inserted by a confirmed import and never updated or deleted in 014 (constitution
Principles III, IV). Previews are temporary and hold the cleaned rows of an uploaded file until it
is confirmed, replaced or expired (research R9).
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
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utc_now
from app.models.base import Base

PREVIEW_STATUSES = ("fetching", "ready", "failed")
IMAGE_SIDES = ("front", "back")


def _ts() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )


class LegacyImport(Base):
    __tablename__ = "legacy_imports"
    __table_args__ = (
        CheckConstraint("char_length(file_name) <= 200", name="legacy_imports_file_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _ts()
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False)
    imported: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False)
    already_imported: Mapped[int] = mapped_column(Integer, nullable=False)
    not_counted: Mapped[int] = mapped_column(Integer, nullable=False)
    incomplete: Mapped[int] = mapped_column(Integer, nullable=False)
    corrected: Mapped[int] = mapped_column(Integer, nullable=False)


class LegacySubscriber(Base):
    __tablename__ = "legacy_subscribers"
    __table_args__ = (
        UniqueConstraint("legacy_number", name="legacy_subscribers_legacy_number_key"),
        CheckConstraint(
            "legacy_number ~ '^T3C-[0-9]{3}$'", name="legacy_subscribers_legacy_number"
        ),
        CheckConstraint("phone IS NULL OR phone ~ '^07[0-9]{9}$'", name="legacy_subscribers_phone"),
        Index("legacy_subscribers_phone", "phone", postgresql_where=text("counts_in_check")),
        Index(
            "legacy_subscribers_family_key", "family_key", postgresql_where=text("counts_in_check")
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    import_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("legacy_imports.id"), nullable=False
    )
    legacy_number: Mapped[str] = mapped_column(Text, nullable=False)
    form_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_name: Mapped[str | None] = mapped_column(Text)
    second_name: Mapped[str | None] = mapped_column(Text)
    third_name: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    # As written in the file; `family_number` is the value in use (the file value or the admin's
    # correction) and `family_key` its §6.2 comparison key.
    family_number_file: Mapped[str | None] = mapped_column(Text)
    family_number: Mapped[str | None] = mapped_column(Text)
    family_key: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    phone_file: Mapped[str | None] = mapped_column(Text)
    status_text: Mapped[str | None] = mapped_column(Text)
    # False for «ملغي» / «مرفوض» (system.md 1.19 §12.1): imported, never matched by the check.
    counts_in_check: Mapped[bool] = mapped_column(Boolean, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    incomplete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = _ts()

    images: Mapped[list["LegacyImage"]] = relationship(
        back_populates="subscriber", order_by="LegacyImage.side.desc()"
    )


class LegacyImage(Base):
    __tablename__ = "legacy_images"
    __table_args__ = (
        CheckConstraint("side IN ('front', 'back')", name="legacy_images_side"),
        UniqueConstraint("legacy_subscriber_id", "side", name="legacy_images_subscriber_side_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legacy_subscriber_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("legacy_subscribers.id"), nullable=False
    )
    side: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _ts()

    subscriber: Mapped[LegacySubscriber] = relationship(back_populates="images")


class LegacyImportPreview(Base):
    __tablename__ = "legacy_import_previews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('fetching', 'ready', 'failed')", name="legacy_import_previews_status"
        ),
        Index("legacy_import_previews_owner", "created_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _ts()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    images_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    images_done: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    # The cleaned rows (data-model.md › PreviewRow). Personal data: never logged.
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
