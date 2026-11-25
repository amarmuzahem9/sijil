"""The database mirrors the backup files (specs/016 research R8, data-model.md «Tables»).

Files are the truth: complete snapshots → `backup_runs` (matched on `snapshot_id`), failure
records → failed runs (matched on their run id), drill / external copy / restore / deploy
records → `backup_events`. A succeeded row whose folder is gone becomes `removed`. After a
restore takes the database back in time, the next sync brings every later record back.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backup.retention import read_manifest
from app.backup.store import BackupStore
from app.core.timeutil import utc_now
from app.models import BackupEvent, BackupRun, User
from app.models.backup import EVENT_TYPES

FAILED = "failed"


def history_time(name: str) -> datetime:
    return datetime.strptime(name[:22], "%Y%m%d-%H%M%S-%f").replace(tzinfo=UTC)


def history_type(name: str) -> str:
    return name[23:-5]


def _user_or_none(db: Session, user_id: int | None) -> int | None:
    if user_id is None:
        return None
    return user_id if db.get(User, user_id) is not None else None


def _sync_snapshots(db: Session, store: BackupStore) -> None:
    complete = store.list_snapshots()
    rows = {r.snapshot_id: r for r in db.scalars(select(BackupRun)) if r.snapshot_id}
    for sid in complete:
        manifest = read_manifest(store, sid)
        # A row of that very id may exist without the snapshot_id (a restored database holds
        # its own backup's row, possibly marked failed after the restart): reuse it.
        row = rows.get(sid) or db.get(BackupRun, sid)
        if row is None:
            row = BackupRun(id=sid, snapshot_id=sid, kind=manifest.kind, status="succeeded")
            row.requested_by = _user_or_none(db, manifest.requested_by)
            db.add(row)
        elif manifest.requested_by is not None and row.requested_by is None:
            row.requested_by = _user_or_none(db, manifest.requested_by)
        row.snapshot_id = sid
        row.status = "succeeded"
        row.error_code = None
        row.removed_at = None
        row.started_at = manifest.started_at
        row.finished_at = manifest.finished_at
        row.total_size = manifest.total_size
        row.image_count = len(manifest.images)
        row.counts = {
            "requests": manifest.counts.requests,
            "legacy_subscribers": manifest.counts.legacy_subscribers,
            "sas_subscribers": manifest.counts.sas_subscribers,
            "users": manifest.counts.users,
        }
    present = set(complete)
    for sid, row in rows.items():
        if row.status == "succeeded" and sid not in present:
            row.status = "removed"
            row.removed_at = utc_now()


def _sync_failures(db: Session, records: list[tuple[str, dict[str, Any]]]) -> None:
    for _, data in records:
        row = db.get(BackupRun, data["run_id"])
        if row is not None and row.status in ("succeeded", "removed"):
            continue
        if row is None:
            row = BackupRun(id=data["run_id"], kind=data["kind"], status=FAILED)
            db.add(row)
        row.status = FAILED
        row.kind = data["kind"]
        row.error_code = data["error_code"]
        row.started_at = datetime.fromisoformat(data["started_at"]) if data["started_at"] else None
        row.finished_at = (
            datetime.fromisoformat(data["finished_at"]) if data["finished_at"] else None
        )
        row.requested_by = _user_or_none(db, data.get("requested_by"))
        db.flush()


def _sync_events(db: Session, records: list[tuple[str, dict[str, Any]]]) -> None:
    for name, data in records:
        event = db.get(BackupEvent, name)
        if event is None:
            event = BackupEvent(id=name, type=history_type(name), at=history_time(name))
            db.add(event)
        event.result = data["result"]
        event.snapshot_id = data.get("snapshot_id")
        event.details = data.get("details", {})


def sync(db: Session, store: BackupStore) -> None:
    history = store.read_history()
    _sync_snapshots(db, store)
    db.flush()
    _sync_failures(db, [(n, d) for n, d in history if history_type(n) == FAILED])
    _sync_events(db, [(n, d) for n, d in history if history_type(n) in EVENT_TYPES])
    db.flush()
