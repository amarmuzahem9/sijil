"""One encrypted snapshot of the database and every stored image (specs/016 research R3, R4).

1. Pass 1: store every image file not yet stored (the slow part; the app keeps running).
2. One `REPEATABLE READ` transaction exports its snapshot; `pg_dump --snapshot` dumps exactly
   that moment, piped into `age`; the same transaction reads the referenced image names, the
   Alembic revision and the counts.
3. Pass 2: store referenced files uploaded meanwhile. The app unlinks files only after its
   commit, so a referenced file can be missing only if it was created and deleted inside the
   window: the snapshot then fails with `missing_images` and is retried once.

The server never decrypts: everything is encrypted to the public recipient. Logs carry ids,
sizes and counts only (Principle II).
"""

import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.backup import crypto
from app.backup.errors import SnapshotFailed
from app.backup.manifest import IMAGE_NAME, Counts, DumpEntry, ImageEntry, Manifest
from app.backup.store import DUMP, MANIFEST, BackupStore, snapshot_id
from app.core.timeutil import utc_now

log = logging.getLogger("sijil.backup")

_REFERENCES = text(
    "SELECT file_name FROM draft_images "
    "UNION SELECT file_name FROM request_images "
    "UNION SELECT file_name FROM legacy_images "
    "UNION SELECT image_file_name FROM card_readings"
)
_COUNTS = text(
    "SELECT (SELECT count(*) FROM requests), (SELECT count(*) FROM drafts), "
    "(SELECT count(*) FROM legacy_subscribers), (SELECT count(*) FROM sas_subscribers), "
    "(SELECT count(*) FROM users), (SELECT count(*) FROM audit_log)"
)

Hooks = dict[str, Callable[[], None]]


@dataclass(frozen=True)
class SnapshotConfig:
    store: BackupStore
    uploads: Path
    recipient: str
    database_url: str
    app_commit: str


def libpq_env(database_url: str) -> tuple[list[str], dict[str, str]]:
    """Connection arguments for pg_dump/pg_restore. The password goes in the environment, never
    in argv (visible to `ps`)."""
    url = make_url(database_url)
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    args = ["--host", url.host or "localhost", "--port", str(url.port or 5432)]
    if url.username:
        args += ["--username", url.username]
    return args + ["--dbname", url.database or ""], env


def stored_files(uploads: Path) -> list[Path]:
    """The image files in storage, without uploads in progress or foreign files."""
    if not uploads.is_dir():
        return []
    return sorted(p for p in uploads.iterdir() if IMAGE_NAME.fullmatch(p.name) and p.is_file())


def _store_file(store: BackupStore, path: Path, recipient: str) -> tuple[ImageEntry, bool] | None:
    try:
        result = store.put_image(path, recipient)
    except FileNotFoundError:
        return None  # deleted after the listing: its row was gone before the snapshot
    except crypto.CryptoError as exc:
        raise SnapshotFailed("encrypt_failed", "image") from exc
    return result.entry, result.written


def _dump(cfg: SnapshotConfig, snapshot: str, dst: Path) -> None:
    args, env = libpq_env(cfg.database_url)
    proc = subprocess.Popen(
        ["pg_dump", "--format=custom", "--no-owner", f"--snapshot={snapshot}", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.stdout is not None and proc.stderr is not None
    try:
        crypto.encrypt_stream(proc.stdout, dst, cfg.recipient)
    except crypto.CryptoError as exc:
        proc.kill()
        proc.wait()
        raise SnapshotFailed("encrypt_failed", "dump") from exc
    finally:
        proc.stdout.close()
    err = proc.stderr.read()
    proc.stderr.close()
    if proc.wait() != 0:
        dst.unlink(missing_ok=True)
        # pg_dump's message names objects, not row values.
        raise SnapshotFailed("dump_failed", err.decode(errors="replace").strip()[-200:])


def take_snapshot(
    cfg: SnapshotConfig,
    kind: str,
    *,
    requested_by: int | None = None,
    hooks: Hooks | None = None,
    started: datetime | None = None,
) -> Manifest:
    hooks = hooks or {}
    store = cfg.store
    started = (started or utc_now()).replace(microsecond=0)
    sid = snapshot_id(started, kind)
    while store.snapshot_dir(sid).exists():  # two snapshots of one kind in the same second
        started += timedelta(seconds=1)
        sid = snapshot_id(started, kind)
    folder = store.begin_snapshot(sid)
    try:
        entries: dict[str, ImageEntry] = {}
        new_bytes = 0
        for path in stored_files(cfg.uploads):
            stored = _store_file(store, path, cfg.recipient)
            if stored is not None:
                entries[path.name] = stored[0]
                if stored[1]:
                    new_bytes += store.image_path(path.name).stat().st_size
        if "after_pass1" in hooks:
            hooks["after_pass1"]()

        engine = create_engine(cfg.database_url, hide_parameters=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                exported = conn.execute(text("SELECT pg_export_snapshot()")).scalar_one()
                referenced = {name for (name,) in conn.execute(_REFERENCES) if name}
                counts = Counts(*conn.execute(_COUNTS).one())
                revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                _dump(cfg, exported, folder / DUMP)
                conn.rollback()
        finally:
            engine.dispose()
        if "after_snapshot" in hooks:
            hooks["after_snapshot"]()

        missing = 0
        for name in sorted(referenced - set(entries)):
            path = cfg.uploads / name
            stored = _store_file(store, path, cfg.recipient) if IMAGE_NAME.fullmatch(name) else None
            if stored is None:
                missing += 1
                continue
            entries[name] = stored[0]
            if stored[1]:
                new_bytes += store.image_path(name).stat().st_size
        if missing:
            raise SnapshotFailed("missing_images", f"{missing} referenced image(s) missing")

        # Verify what was written before calling it a backup (FR-015a).
        dump_path = folder / DUMP
        dump = DumpEntry(size=dump_path.stat().st_size, sha256_enc=crypto.sha256_file(dump_path))
        for entry in entries.values():
            obj = store.image_path(entry.name)
            if not obj.exists():
                raise SnapshotFailed("verify_failed", "image object missing")
        manifest = Manifest(
            id=sid,
            kind=kind,
            started_at=started,
            finished_at=max(utc_now(), started),
            app_commit=cfg.app_commit,
            alembic_revision=revision or "",
            counts=counts,
            dump=dump,
            images=sorted(entries.values(), key=lambda e: e.name),
            missing_referenced=0,
            total_size=dump.size + new_bytes,
            requested_by=requested_by,
        )
        store.write_json_atomic(folder / MANIFEST, manifest.to_json())
        store.mark_done(sid)
    except SnapshotFailed:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise SnapshotFailed("internal", type(exc).__name__) from exc
    log.info(
        "backup snapshot %s: %d images, %d bytes new",
        sid,
        len(manifest.images),
        manifest.total_size,
    )
    return manifest


def take_with_retry(
    cfg: SnapshotConfig,
    kind: str,
    *,
    requested_by: int | None = None,
    hooks: Hooks | None = None,
    on_attempt_failed: Callable[[str], None] | None = None,
    started: datetime | None = None,
) -> Manifest:
    """`take_snapshot`, retried once at once when an image vanished inside the window (R4)."""
    try:
        return take_snapshot(cfg, kind, requested_by=requested_by, hooks=hooks, started=started)
    except SnapshotFailed as exc:
        if exc.code != "missing_images":
            raise
        log.warning("backup snapshot: %s, retrying once", exc.code)
        if on_attempt_failed is not None:
            on_attempt_failed(exc.code)
    return take_snapshot(cfg, kind, requested_by=requested_by, hooks=hooks, started=started)
