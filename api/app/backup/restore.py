"""Restore and the restore drill (specs/016 FR-012–FR-015, research R7, R9).

`verify` needs no passphrase: it checks the snapshot is complete and that every encrypted file
still has the hash the manifest recorded. `stage_images` decrypts the images into a staging
folder and checks each plaintext hash, before anything live is touched. `restore_database`
recreates the database from `age -d | pg_restore`, so the decrypted dump never lands on disk.
`verify_restored` is the drill's comparison: counts, every image with its hash, and no row
pointing at a missing file. Records carry ids, counts and reasons only.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.backup import crypto
from app.backup.manifest import IMAGE_NAME, Counts, Manifest, ManifestError
from app.backup.snapshot import _COUNTS, _REFERENCES, libpq_env
from app.backup.store import DONE, DUMP, MANIFEST, BackupStore, parse_snapshot_id

log = logging.getLogger("sijil.backup")

API_ROOT = Path(__file__).resolve().parents[2]


class RestoreRefused(Exception):
    """The restore cannot go on; nothing live was changed by the step that raised it."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# --- Checks without the passphrase ----------------------------------------------------------


def verify(store: BackupStore, sid: str) -> Manifest:
    try:
        folder = store.snapshot_dir(sid)
    except ValueError as exc:
        raise RestoreRefused("not_found") from exc
    if not folder.is_dir():
        raise RestoreRefused("not_found")
    if not (folder / DONE).exists() or not (folder / MANIFEST).exists():
        raise RestoreRefused("incomplete")
    try:
        manifest = Manifest.from_json((folder / MANIFEST).read_text(encoding="utf-8"))
    except ManifestError as exc:
        raise RestoreRefused("damaged", "manifest") from exc
    dump = folder / DUMP
    if not dump.exists() or crypto.sha256_file(dump) != manifest.dump.sha256_enc:
        raise RestoreRefused("damaged", "database dump")
    for entry in manifest.images:
        obj = store.image_path(entry.name)
        if not obj.exists() or crypto.sha256_file(obj) != entry.sha256_enc:
            raise RestoreRefused("damaged", "image object")
    return manifest


def known_revisions() -> set[str]:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    return {rev.revision for rev in ScriptDirectory.from_config(cfg).walk_revisions()}


def check_revision(manifest: Manifest) -> None:
    """A backup from a newer version of the app cannot be restored onto this code (R7)."""
    if manifest.alembic_revision not in known_revisions():
        raise RestoreRefused("revision_unknown", manifest.alembic_revision)


# --- Steps with the identity ----------------------------------------------------------------


def stage_images(store: BackupStore, manifest: Manifest, identity: Path, dst: Path) -> int:
    for entry in manifest.images:
        target = dst / entry.name
        try:
            crypto.decrypt_file(store.image_path(entry.name), target, identity)
        except crypto.CryptoError as exc:
            raise RestoreRefused("decrypt_failed", "image") from exc
        if crypto.sha256_file(target) != entry.sha256_plain:
            raise RestoreRefused("damaged", "image content")
    return len(manifest.images)


def restore_database(
    store: BackupStore, manifest: Manifest, identity: Path, database_url: str
) -> None:
    """Drop and recreate the database, then restore the dump into it."""
    crypto._check_identity(identity)
    url = make_url(database_url)
    admin = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()
    args, env = libpq_env(database_url)
    decrypt = subprocess.Popen(
        [
            "age",
            "--decrypt",
            "--identity",
            str(identity),
            str(store.snapshot_dir(manifest.id) / DUMP),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert decrypt.stdout is not None and decrypt.stderr is not None
    pg = subprocess.run(
        ["pg_restore", "--no-owner", "--exit-on-error", *args],
        stdin=decrypt.stdout,
        capture_output=True,
        env=env,
    )
    decrypt.stdout.close()
    age_err = decrypt.stderr.read()
    decrypt.stderr.close()
    if decrypt.wait() != 0:
        raise RestoreRefused("decrypt_failed", age_err.decode(errors="replace").strip()[-200:])
    if pg.returncode != 0:
        # pg_restore names objects, not row values.
        raise RestoreRefused("restore_failed", pg.stderr.decode(errors="replace").strip()[-200:])
    log.info("backup restore: database restored from %s", manifest.id)


def swap_uploads(staged: Path, live: Path) -> None:
    """Replace the live image storage with the staged, verified images."""
    for path in live.iterdir():
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    for path in staged.iterdir():
        if IMAGE_NAME.fullmatch(path.name):
            shutil.copy2(path, live / path.name)
            os.chmod(live / path.name, 0o600)


# --- The drill's comparison -----------------------------------------------------------------


def database_counts(database_url: str) -> Counts:
    engine = create_engine(database_url, hide_parameters=True)
    try:
        with engine.connect() as conn:
            return Counts(*conn.execute(_COUNTS).one())
    finally:
        engine.dispose()


def _referenced(database_url: str) -> set[str]:
    engine = create_engine(database_url, hide_parameters=True)
    try:
        with engine.connect() as conn:
            return {name for (name,) in conn.execute(_REFERENCES) if name}
    finally:
        engine.dispose()


@dataclass
class DrillResult:
    passed: bool
    reason: str | None
    compared: dict[str, Any] = field(default_factory=dict)


def verify_restored(database_url: str, uploads: Path, manifest: Manifest) -> DrillResult:
    found = asdict(database_counts(database_url))
    expected = asdict(manifest.counts)
    compared: dict[str, Any] = {
        name: {"expected": expected[name], "found": found[name]} for name in expected
    }
    present = [e for e in manifest.images if (uploads / e.name).is_file()]
    changed = [e for e in present if crypto.sha256_file(uploads / e.name) != e.sha256_plain]
    on_disk = {p.name for p in uploads.iterdir() if p.is_file()}
    missing_referenced = len(_referenced(database_url) - on_disk)
    compared["images"] = {"expected": len(manifest.images), "found": len(present)}
    compared["missing_referenced"] = missing_referenced
    reason = None
    if found != expected:
        reason = "count_mismatch"
    elif len(present) != len(manifest.images):
        reason = "images_missing"
    elif changed:
        reason = "image_hash_mismatch"
    elif missing_referenced:
        reason = "referenced_missing"
    return DrillResult(passed=reason is None, reason=reason, compared=compared)


def record_drill(
    store: BackupStore, sid: str, result: DrillResult, *, at: datetime, source: str
) -> str:
    parse_snapshot_id(sid)
    return store.write_history(
        "drill",
        {
            "result": "passed" if result.passed else "failed",
            "snapshot_id": sid,
            "details": {"source": source, "reason": result.reason, "compared": result.compared},
        },
        at=at,
    )
