"""SAS subscribers from the SAS export (specs/015 data-model.md). Mirrors migration 0018.

A SAS subscriber is not a request: no marketer, no status in the request flow, no national ID,
family number or images. Rows are added and updated only by a confirmed import, keyed by the
upper-case username, and never deleted (constitution Principle III); every update leaves an
append-only `SasSubscriberChange`. No model has, or may ever get, a password column (research R3).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now
from app.models.base import Base

_PHONE = "~ '^07[0-9]{9}$'"


def _ts() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )


def _tower() -> Mapped[int | None]:
    return mapped_column(BigInteger, ForeignKey("towers.id", ondelete="RESTRICT"))


class SasImport(Base):
    __tablename__ = "sas_imports"
    __table_args__ = (
        CheckConstraint("char_length(file_name) <= 200", name="sas_imports_file_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # The «حسب آخر استيراد» date of the rows it wrote.
    created_at: Mapped[datetime] = _ts()
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False)
    added: Mapped[int] = mapped_column(Integer, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_marked: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_cleared: Mapped[int] = mapped_column(Integer, nullable=False)
    without_phone: Mapped[int] = mapped_column(Integer, nullable=False)
    prefixes_mapped: Mapped[int] = mapped_column(Integer, nullable=False)


class SasSubscriber(Base):
    __tablename__ = "sas_subscribers"
    __table_args__ = (
        UniqueConstraint("username_key", name="sas_subscribers_username_key"),
        CheckConstraint(f"phone IS NULL OR phone {_PHONE}", name="sas_subscribers_phone"),
        CheckConstraint(
            f"username_phone IS NULL OR username_phone {_PHONE}",
            name="sas_subscribers_username_phone",
        ),
        Index("sas_subscribers_phone", "phone"),
        Index("sas_subscribers_username_phone", "username_phone"),
        Index("sas_subscribers_tower_id", "tower_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # As written; `username_key` (upper-case, Latin digits) is the key of a re-import (§12.2).
    username: Mapped[str] = mapped_column(Text, nullable=False)
    username_key: Mapped[str] = mapped_column(Text, nullable=False)
    sas_id: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Both phones count in the check (system.md 1.20 §12.2; research R5).
    phone: Mapped[str | None] = mapped_column(Text)
    phone_file: Mapped[str | None] = mapped_column(Text)
    username_phone: Mapped[str | None] = mapped_column(Text)
    tower_prefix: Mapped[str | None] = mapped_column(Text)
    tower_id: Mapped[int | None] = _tower()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sas_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    group_name: Mapped[str | None] = mapped_column(Text)
    parent_name: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    first_import_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sas_imports.id"), nullable=False
    )
    last_import_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sas_imports.id"), nullable=False
    )
    # «غير موجود في آخر ملف»: set by the first import whose file lacks the username, cleared when
    # a later file holds it again. The row keeps counting in the check (FR-022).
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    missing_import_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sas_imports.id"))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class SasSubscriberChange(Base):
    """Append-only: the changed fields of one subscriber in one import (research R10)."""

    __tablename__ = "sas_subscriber_changes"
    __table_args__ = (Index("sas_subscriber_changes_subscriber", "sas_subscriber_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sas_imports.id"), nullable=False)
    sas_subscriber_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sas_subscribers.id"), nullable=False
    )
    before: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _ts()


class SasTowerMapping(Base):
    """A username prefix with no tower by the rule, and the admin's choice (NULL = «بلا برج»)."""

    __tablename__ = "sas_tower_mappings"

    prefix: Mapped[str] = mapped_column(Text, primary_key=True)
    tower_id: Mapped[int | None] = _tower()
    set_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    set_at: Mapped[datetime] = _ts()
    import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sas_imports.id"), nullable=False)


class SasImportPreview(Base):
    __tablename__ = "sas_import_previews"
    __table_args__ = (Index("sas_import_previews_owner", "created_by"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _ts()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    # The cleaned rows (data-model.md › SasPreviewRow), never a password. Personal data: never
    # logged.
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    prefixes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    missing_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
