"""The `backup` service loop (specs/016 FR-005, FR-008, FR-016, research R5, R6, R8).

Every 15 seconds: heartbeat and disk space into `backup_status`; a manual backup the main admin
requested; the nightly backup when due; then the mirror rebuilt from the files. One operation at
a time, across this loop and every operator command, through a PostgreSQL advisory lock.
"""

import logging
import os
import shutil
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.backup import mirror, retention
from app.backup.errors import BackupBusy, SnapshotFailed
from app.backup.schedule import nightly_due
from app.backup.snapshot import SnapshotConfig, take_with_retry
from app.backup.store import BackupStore, parse_snapshot_id, snapshot_id
from app.core.timeutil import utc_now
from app.models import BackupRun, BackupStatus

log = logging.getLogger("sijil.backup")

BACKUP_LOCK = 160_016
LOOP_SECONDS = 15
# Touched after every loop; the compose healthcheck reads its age (no database query needed).
HEARTBEAT_FILE = Path("/tmp/backup-heartbeat")


class BackupService:
    def __init__(
        self,
        *,
        sessions: sessionmaker[Session],
        store: BackupStore,
        uploads: Path,
        recipient: str,
        database_url: str,
        nightly_minutes: int,
        min_free_bytes: int,
        external_dir: str,
        app_commit: str,
    ) -> None:
        self.sessions = sessions
        self.store = store
        self.uploads = uploads
        self.recipient = recipient
        self.database_url = database_url
        self.nightly_minutes = nightly_minutes
        self.min_free_bytes = min_free_bytes
        self.external_dir = external_dir
        self.app_commit = app_commit
        self._lock_engine = create_engine(database_url, hide_parameters=True, pool_size=1)
        self._dir_bytes: int | None = None
        store.ensure_layout()

    @classmethod
    def from_settings(cls) -> "BackupService":
        from app.config import get_settings
        from app.db import get_sessionmaker

        s = get_settings()
        return cls(
            sessions=get_sessionmaker(),
            store=BackupStore(s.backup_dir),
            uploads=Path(s.uploads_dir),
            recipient=s.backup_age_recipient,
            database_url=s.database_url,
            nightly_minutes=s.backup_nightly_minutes,
            min_free_bytes=int(s.backup_min_free_gb * retention.GB),
            external_dir=s.backup_external_dir,
            app_commit=os.environ.get("APP_COMMIT", "unknown"),
        )

    # --- Lock -----------------------------------------------------------------------------

    @contextmanager
    def lock(self) -> Iterator[None]:
        with self._lock_engine.connect() as conn:
            got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": BACKUP_LOCK})
            if not got.scalar_one():
                raise BackupBusy()
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": BACKUP_LOCK})
                conn.commit()

    # --- One backup -----------------------------------------------------------------------

    def _failure_record(self, row: BackupRun) -> None:
        self.store.write_history(
            "failed",
            {
                "run_id": row.id,
                "kind": row.kind,
                "error_code": row.error_code,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "requested_by": row.requested_by,
            },
            at=row.finished_at or utc_now(),
        )

    def _free_bytes(self) -> int:
        return shutil.disk_usage(self.store.root).free

    def run(
        self,
        kind: str,
        *,
        run_id: str | None = None,
        requested_by: int | None = None,
        now: datetime | None = None,
    ) -> BackupRun:
        """Take one backup under the lock. Raises BackupBusy, or SnapshotFailed after recording
        the failure (row + history file)."""
        with self.lock():
            return self._run_locked(kind, run_id=run_id, requested_by=requested_by, now=now)

    def _run_locked(
        self, kind: str, *, run_id: str | None, requested_by: int | None, now: datetime | None
    ) -> BackupRun:
        started = (now or utc_now()).replace(microsecond=0)
        sid = snapshot_id(started, kind)
        while self.store.snapshot_dir(sid).exists():
            started += timedelta(seconds=1)
            sid = snapshot_id(started, kind)
        with self.sessions() as db:
            row = db.get(BackupRun, run_id) if run_id else None
            if row is None:
                row = BackupRun(id=run_id or sid, kind=kind, requested_by=requested_by)
                db.add(row)
            row.status = "running"
            row.snapshot_id = sid
            row.started_at = started
            db.commit()
            try:
                if not self.recipient:
                    raise SnapshotFailed("no_key")
                estimate = retention.estimate_bytes(
                    self.store, self.uploads, last_dump_size=retention.last_dump_size(self.store)
                )
                retention.check_disk(
                    free_bytes=self._free_bytes(),
                    estimate=estimate,
                    min_free_bytes=self.min_free_bytes,
                )
                manifest = take_with_retry(
                    SnapshotConfig(
                        store=self.store,
                        uploads=self.uploads,
                        recipient=self.recipient,
                        database_url=self.database_url,
                        app_commit=self.app_commit,
                    ),
                    kind,
                    requested_by=row.requested_by,
                    started=started,
                )
            except SnapshotFailed as exc:
                row.status = "failed"
                row.snapshot_id = None
                row.error_code = exc.code
                row.finished_at = max(utc_now(), started)
                db.commit()
                self._failure_record(row)
                log.warning("backup %s failed: %s", row.id, exc.code)
                raise
            row.status = "succeeded"
            row.snapshot_id = manifest.id
            row.finished_at = manifest.finished_at
            row.total_size = manifest.total_size
            row.image_count = len(manifest.images)
            row.counts = {
                "requests": manifest.counts.requests,
                "legacy_subscribers": manifest.counts.legacy_subscribers,
                "sas_subscribers": manifest.counts.sas_subscribers,
                "users": manifest.counts.users,
            }
            db.commit()
            retention.apply(self.store, started)
            self._dir_bytes = None
            mirror.sync(db, self.store)
            db.commit()
            return row

    # --- Loop -----------------------------------------------------------------------------

    def recover(self) -> None:
        """On start: a run left `running` by a crash becomes failed (no live lock holds it)."""
        try:
            with self.lock(), self.sessions() as db:
                for row in db.scalars(select(BackupRun).where(BackupRun.status == "running")):
                    row.status = "failed"
                    row.error_code = "internal"
                    row.snapshot_id = None
                    row.finished_at = utc_now()
                    db.flush()
                    self._failure_record(row)
                db.commit()
        except BackupBusy:
            pass  # an operator command is running; it owns its rows

    def _backup_dir_bytes(self) -> int:
        if self._dir_bytes is None:
            self._dir_bytes = sum(
                p.stat().st_size for p in self.store.root.rglob("*") if p.is_file()
            )
        return self._dir_bytes

    def heartbeat(self, now: datetime) -> None:
        usage = shutil.disk_usage(self.store.root)
        hours, minutes = divmod(self.nightly_minutes, 60)
        with self.sessions() as db:
            status = db.get(BackupStatus, 1) or BackupStatus(id=1)
            status.heartbeat_at = now
            status.free_bytes = usage.free
            status.total_bytes = usage.total
            status.min_free_bytes = self.min_free_bytes
            status.nightly_at = f"{hours:02d}:{minutes:02d}"
            status.external_dir = self.external_dir
            status.backup_dir_bytes = self._backup_dir_bytes()
            status.key_configured = bool(self.recipient)
            db.add(status)
            db.commit()

    def nightly_attempts(self) -> list[tuple[datetime, bool]]:
        attempts = [
            (parse_snapshot_id(sid)[0], True)
            for sid in self.store.list_snapshots()
            if sid.endswith("-nightly")
        ]
        for name, data in self.store.read_history():
            if mirror.history_type(name) == "failed" and data.get("kind") == "nightly":
                at = data.get("started_at") or data.get("finished_at")
                if at:
                    attempts.append((datetime.fromisoformat(at), False))
        return attempts

    def iteration(self, now: datetime | None = None) -> None:
        now = now or utc_now()
        self.heartbeat(now)
        with self.sessions() as db:
            requested = db.scalar(
                select(BackupRun)
                .where(BackupRun.status == "requested")
                .order_by(BackupRun.created_at)
            )
            request = (requested.id, requested.requested_by) if requested else None
        if request is not None:
            try:
                self.run("manual", run_id=request[0], requested_by=request[1], now=now)
            except BackupBusy:
                pass  # stays requested; tried again next loop
            except SnapshotFailed:
                pass  # recorded
        if self.recipient and nightly_due(now, self.nightly_minutes, self.nightly_attempts()):
            try:
                self.run("nightly", now=now)
            except SnapshotFailed:
                pass  # recorded (BackupBusy included: the schedule catches up)
        try:
            with self.lock(), self.sessions() as db:
                mirror.sync(db, self.store)
                db.commit()
        except BackupBusy:
            pass

    def serve(self) -> None:  # pragma: no cover - the loop itself; iteration() is tested
        if not self.recipient:
            log.warning("لم يُضبط مفتاح النسخ (BACKUP_AGE_RECIPIENT): no backup will be taken")
        self.recover()
        while True:
            try:
                self.iteration()
            except Exception:  # keep the service alive; the heartbeat shows trouble
                log.exception("backup loop iteration failed")
            else:
                HEARTBEAT_FILE.touch()
            time.sleep(LOOP_SECONDS)


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:12]}"
