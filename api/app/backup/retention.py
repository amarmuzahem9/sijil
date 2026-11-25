"""Retention, image garbage collection and the disk guard (specs/016 FR-006, FR-009, R6).

After a successful backup: snapshots older than 30 days (all kinds) go, never the newest
complete one; incomplete folders older than a day go; then image objects no kept snapshot needs.
A failed run removes nothing.
"""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.backup.errors import SnapshotFailed
from app.backup.manifest import Manifest
from app.backup.snapshot import stored_files
from app.backup.store import MANIFEST, BackupStore, parse_snapshot_id

log = logging.getLogger("sijil.backup")

RETENTION = timedelta(days=30)
INCOMPLETE_AGE = timedelta(days=1)
GB = 1024**3


def select_removals(
    complete: list[str], incomplete: list[str], now: datetime, *, last_run_succeeded: bool
) -> list[str]:
    if not last_run_succeeded:
        return []
    ordered = sorted(complete, key=lambda sid: parse_snapshot_id(sid)[0])
    newest = ordered[-1] if ordered else None
    old = [sid for sid in ordered if sid != newest and now - parse_snapshot_id(sid)[0] > RETENTION]
    stale = [sid for sid in incomplete if now - parse_snapshot_id(sid)[0] > INCOMPLETE_AGE]
    return sorted(old + stale, key=lambda sid: parse_snapshot_id(sid)[0])


def unreferenced_objects(stored: set[str], kept: list[Manifest]) -> set[str]:
    needed: set[str] = set()
    for manifest in kept:
        needed |= manifest.image_names
    return stored - needed


def read_manifest(store: BackupStore, sid: str) -> Manifest:
    return Manifest.from_json((store.snapshot_dir(sid) / MANIFEST).read_text(encoding="utf-8"))


@dataclass
class RetentionResult:
    removed_snapshots: list[str] = field(default_factory=list)
    removed_objects: list[str] = field(default_factory=list)


def apply(store: BackupStore, now: datetime) -> RetentionResult:
    complete = store.list_snapshots()
    incomplete = [s for s in store.list_snapshots(complete_only=False) if s not in complete]
    result = RetentionResult(
        removed_snapshots=select_removals(complete, incomplete, now, last_run_succeeded=True)
    )
    for sid in result.removed_snapshots:
        shutil.rmtree(store.snapshot_dir(sid), ignore_errors=True)
    kept = [read_manifest(store, sid) for sid in store.list_snapshots()]
    for name in sorted(unreferenced_objects(store.stored_image_names(), kept)):
        store.image_path(name).unlink(missing_ok=True)
        (store.images / f"{name}.age.meta").unlink(missing_ok=True)
        result.removed_objects.append(name)
    if result.removed_snapshots or result.removed_objects:
        log.info(
            "backup retention: %d snapshot(s), %d object(s) removed",
            len(result.removed_snapshots),
            len(result.removed_objects),
        )
    return result


def last_dump_size(store: BackupStore) -> int:
    complete = store.list_snapshots()
    return read_manifest(store, complete[-1]).dump.size if complete else 0


def estimate_bytes(store: BackupStore, uploads: Path, *, last_dump_size: int) -> int:
    stored = store.stored_image_names()
    new = sum(p.stat().st_size for p in stored_files(uploads) if p.name not in stored)
    return new + last_dump_size


def check_disk(
    *,
    free_bytes: int,
    estimate: int,
    min_free_gb: float | None = None,
    min_free_bytes: int | None = None,
) -> None:
    margin = min_free_bytes if min_free_bytes is not None else int((min_free_gb or 0) * GB)
    if free_bytes - estimate < margin:
        raise SnapshotFailed("disk_low")
