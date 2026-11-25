"""Backup mirror tables (specs/016 data-model.md «Tables (mirror)»). Mirrors migration 0019.

The backup files are the source of truth (research R8); the `backup` service rebuilds these rows
from them, so a restore does not erase the history of later backups. No personal data, no paths
to card images, no key.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now
from app.models.base import Base

RUN_KINDS = ("nightly", "manual", "pre_deploy", "pre_restore")
RUN_STATUSES = ("requested", "running", "succeeded", "failed", "removed")
RUN_ERRORS = (
    "disk_low",
    "missing_images",
    "dump_failed",
    "encrypt_failed",
    "verify_failed",
    "busy",
    "no_key",
    "internal",
)
EVENT_TYPES = ("drill", "external_copy", "restore", "deploy")
EVENT_RESULTS = ("passed", "failed", "succeeded")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class BackupRun(Base):
    __tablename__ = "backup_runs"
    __table_args__ = (
        CheckConstraint(_in("kind", RUN_KINDS), name="backup_runs_kind"),
        CheckConstraint(_in("status", RUN_STATUSES), name="backup_runs_status"),
        CheckConstraint(
            f"error_code IS NULL OR {_in('error_code', RUN_ERRORS)}", name="backup_runs_error_code"
        ),
    )

    # Never changes: `req-<uuid>` for a manual request, otherwise the snapshot id.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # The snapshot folder; null until the run starts. The mirror matches files on it.
    snapshot_id: Mapped[str | None] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_size: Mapped[int | None] = mapped_column(BigInteger)
    image_count: Mapped[int | None] = mapped_column(Integer)
    counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )


class BackupEvent(Base):
    __tablename__ = "backup_events"
    __table_args__ = (
        CheckConstraint(_in("type", EVENT_TYPES), name="backup_events_type"),
        CheckConstraint(_in("result", EVENT_RESULTS), name="backup_events_result"),
    )

    # The history file name, e.g. `20261125-093000-000000-drill.json`.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class BackupStatus(Base):
    __tablename__ = "backup_status"
    __table_args__ = (CheckConstraint("id = 1", name="backup_status_single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    free_bytes: Mapped[int | None] = mapped_column(BigInteger)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    min_free_bytes: Mapped[int | None] = mapped_column(BigInteger)
    nightly_at: Mapped[str] = mapped_column(Text, nullable=False)
    # Configured in .env only; shown read-only (owner decision Q3-A).
    external_dir: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    backup_dir_bytes: Mapped[int | None] = mapped_column(BigInteger)
    # False until BACKUP_AGE_RECIPIENT is set: the service then backs nothing up and says so.
    key_configured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
