"""The weekly copy to the external drive (specs/016 FR-007, research R10).

The operator plugs the drive in and runs `scripts/backup.sh weekly`. The latest successful
snapshot goes to the drive in the same layout as BACKUP_DIR, with only the image objects the
drive does not have yet and `key.age`. Nothing on the drive is ever removed or overwritten.
Free space is checked first; every copied file is re-read against the manifest; DONE is written
last, so a broken copy never looks complete. The record holds no path and no personal data.
"""

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.backup import crypto
from app.backup.retention import read_manifest
from app.backup.store import DONE, DUMP, MANIFEST, BackupStore

log = logging.getLogger("sijil.backup")

MARKER = ".sijil-external"
# Room left on the drive after a copy.
SPACE_MARGIN = 64 * 1024 * 1024


class ExternalCopyFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class CopyResult:
    snapshot_id: str
    objects_new: int
    bytes_copied: int
    already_there: bool


def _copy_file(src: Path, dst: Path) -> None:
    temp = dst.with_name(dst.name + crypto.TEMP_SUFFIX)
    shutil.copyfile(src, temp)
    with temp.open("rb") as f:
        os.fsync(f.fileno())
    os.replace(temp, dst)


def _record(store: BackupStore, at: datetime, result: str, sid: str | None, **details) -> None:
    store.write_history(
        "external_copy", {"result": result, "snapshot_id": sid, "details": details}, at=at
    )


def _plan(store: BackupStore, target: BackupStore, sid: str) -> list[tuple[Path, Path]]:
    """(source, destination) of every file the drive does not hold yet."""
    manifest = read_manifest(store, sid)
    files: list[tuple[Path, Path]] = []
    for entry in manifest.images:
        for suffix in (".age", ".age.meta"):
            src = store.images / f"{entry.name}{suffix}"
            dst = target.images / f"{entry.name}{suffix}"
            if not dst.exists():
                files.append((src, dst))
    folder = target.snapshot_dir(sid)
    if not (folder / DONE).exists():
        for name in (MANIFEST, DUMP):
            files.append((store.snapshot_dir(sid) / name, folder / name))
    return files


def copy(store: BackupStore, target_root: Path, *, at: datetime) -> CopyResult:
    sid: str | None = None
    try:
        if not (target_root / MARKER).is_file():
            raise ExternalCopyFailed("not_marked")
        complete = store.list_snapshots()
        if not complete:
            raise ExternalCopyFailed("no_snapshot")
        sid = complete[-1]
        target = BackupStore(target_root)
        key_on_drive = target.key_path
        if key_on_drive.exists() and key_on_drive.read_bytes() != store.key_path.read_bytes():
            raise ExternalCopyFailed("key_mismatch")

        files = _plan(store, target, sid)
        needed = sum(src.stat().st_size for src, _ in files)
        if not key_on_drive.exists():
            needed += store.key_path.stat().st_size
        if shutil.disk_usage(target_root).free - needed < SPACE_MARGIN:
            raise ExternalCopyFailed("no_space")

        target.ensure_layout(chmod_root=False)
        if not key_on_drive.exists():
            _copy_file(store.key_path, key_on_drive)
        folder = target.snapshot_dir(sid)
        folder.mkdir(exist_ok=True)
        for src, dst in files:
            _copy_file(src, dst)

        # Re-read what is on the drive before calling it a copy.
        manifest = read_manifest(target, sid)
        if crypto.sha256_file(folder / DUMP) != manifest.dump.sha256_enc:
            raise ExternalCopyFailed("verify_failed")
        for entry in manifest.images:
            if crypto.sha256_file(target.image_path(entry.name)) != entry.sha256_enc:
                raise ExternalCopyFailed("verify_failed")
        if key_on_drive.read_bytes() != store.key_path.read_bytes():
            raise ExternalCopyFailed("verify_failed")
        already = not files
        if not (folder / DONE).exists():
            target.mark_done(sid)
    except ExternalCopyFailed as exc:
        _record(store, at, "failed", sid, reason=exc.code)
        log.warning("external copy failed: %s", exc.code)
        raise
    except OSError as exc:
        _record(store, at, "failed", sid, reason="write_failed")
        raise ExternalCopyFailed("write_failed") from exc
    objects_new = sum(1 for _, dst in files if dst.name.endswith(".jpg.age"))
    result = CopyResult(
        snapshot_id=sid,
        objects_new=objects_new,
        bytes_copied=needed,
        already_there=already,
    )
    _record(
        store,
        at,
        "succeeded",
        sid,
        objects_new=objects_new,
        bytes_copied=needed,
        already_there=already,
    )
    log.info("external copy %s: %d new objects, %d bytes", sid, objects_new, needed)
    return result
