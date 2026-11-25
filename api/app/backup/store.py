"""Backup folder layout (specs/016 research R3, data-model.md «Files»).

```text
BACKUP_DIR/
├── key.age                          # passphrase-protected identity (never plaintext)
├── images/<32 hex>.jpg.age          # one encrypted object per stored image, written once
├── images/<32 hex>.jpg.age.meta     # its size and hashes (plaintext, no personal data)
├── snapshots/<id>/db.dump.age, manifest.json, DONE
└── history/<utc time>-<type>.json   # drills, external copies, restores, deploys, failures
```

Image names are random (`<uuid4 hex>.jpg`, specs/005 R6) and never change, so an object is
encrypted once and shared by every snapshot that needs it. Everything is mode 700/600.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.backup import crypto
from app.backup.manifest import IMAGE_NAME, KINDS, ImageEntry

_ID = re.compile(r"(\d{8}-\d{6})-(" + "|".join(KINDS) + r")")
_HISTORY = re.compile(r"\d{8}-\d{6}-\d{6}-[a-z_]+\.json")
_HISTORY_TYPE = re.compile(r"[a-z_]+")
DONE = "DONE"
DUMP = "db.dump.age"
MANIFEST = "manifest.json"


def snapshot_id(started: datetime, kind: str) -> str:
    if started.tzinfo is None or started.utcoffset() != UTC.utcoffset(None):
        raise ValueError("snapshot time must be UTC")
    if kind not in KINDS:
        raise ValueError("unknown snapshot kind")
    return f"{started:%Y%m%d-%H%M%S}-{kind}"


def parse_snapshot_id(value: str) -> tuple[datetime, str]:
    match = _ID.fullmatch(value)
    if not match:
        raise ValueError("not a snapshot id")
    started = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=UTC)
    return started, match.group(2)


def check_image_name(name: str) -> str:
    if not IMAGE_NAME.fullmatch(name):
        raise ValueError("not a stored image name")
    return name


@dataclass(frozen=True)
class PutResult:
    entry: ImageEntry
    written: bool


class BackupStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.images = self.root / "images"
        self.snapshots = self.root / "snapshots"
        self.history = self.root / "history"
        self.key_path = self.root / "key.age"

    def ensure_layout(self, *, chmod_root: bool = True) -> None:
        """Create the folders (mode 700). `chmod_root=False` for the external drive, whose mount
        point belongs to root: only the folders created here are ours."""
        self.root.mkdir(parents=True, exist_ok=True)
        if chmod_root:
            try:
                os.chmod(self.root, 0o700)
            except PermissionError:
                # A bound folder we do not own (Docker Desktop on a developer machine). On the
                # server, deploy.sh requires BACKUP_DIR to be uid 10001 with mode 700.
                pass
        for path in (self.images, self.snapshots, self.history):
            path.mkdir(exist_ok=True)
            os.chmod(path, 0o700)

    # --- JSON -----------------------------------------------------------------------------

    def write_json_atomic(self, target: Path, data: dict[str, Any] | str) -> None:
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=1)
        temp = target.with_name(target.name + crypto.TEMP_SUFFIX)
        temp.write_text(text, encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, target)

    # --- Images ---------------------------------------------------------------------------

    def image_path(self, name: str) -> Path:
        return self.images / f"{check_image_name(name)}.age"

    def _meta_path(self, name: str) -> Path:
        return self.images / f"{check_image_name(name)}.age.meta"

    def image_entry(self, name: str) -> ImageEntry | None:
        obj, meta = self.image_path(name), self._meta_path(name)
        if not (obj.exists() and meta.exists()):
            return None
        data = json.loads(meta.read_text(encoding="utf-8"))
        return ImageEntry(name=name, **data)

    def put_image(self, src: Path, recipient: str, name: str | None = None) -> PutResult:
        """Encrypt `src` as the object `name` (default: its file name) unless already stored."""
        name = check_image_name(name if name is not None else src.name)
        existing = self.image_entry(name)
        if existing is not None:
            return PutResult(entry=existing, written=False)
        sha_plain = crypto.sha256_file(src)
        size = src.stat().st_size
        obj = self.image_path(name)
        crypto.encrypt_file(src, obj, recipient)
        entry = ImageEntry(
            name=name, size=size, sha256_plain=sha_plain, sha256_enc=crypto.sha256_file(obj)
        )
        self.write_json_atomic(
            self._meta_path(name),
            {"size": size, "sha256_plain": sha_plain, "sha256_enc": entry.sha256_enc},
        )
        return PutResult(entry=entry, written=True)

    def stored_image_names(self) -> set[str]:
        return {
            p.name[: -len(".age.meta")]
            for p in self.images.glob("*.jpg.age.meta")
            if IMAGE_NAME.fullmatch(p.name[: -len(".age.meta")])
        }

    # --- Snapshots ------------------------------------------------------------------------

    def snapshot_dir(self, sid: str) -> Path:
        parse_snapshot_id(sid)
        return self.snapshots / sid

    def begin_snapshot(self, sid: str) -> Path:
        path = self.snapshot_dir(sid)
        path.mkdir(mode=0o700)
        os.chmod(path, 0o700)
        return path

    def mark_done(self, sid: str) -> None:
        done = self.snapshot_dir(sid) / DONE
        done.write_text("", encoding="utf-8")
        os.chmod(done, 0o600)

    def is_complete(self, sid: str) -> bool:
        return (self.snapshot_dir(sid) / DONE).exists()

    def list_snapshots(self, complete_only: bool = True) -> list[str]:
        if not self.snapshots.is_dir():
            return []
        ids = [p.name for p in self.snapshots.iterdir() if p.is_dir() and _ID.fullmatch(p.name)]
        if complete_only:
            ids = [sid for sid in ids if self.is_complete(sid)]
        return sorted(ids, key=lambda sid: (sid[:15], sid))

    # --- History --------------------------------------------------------------------------

    def write_history(self, type_: str, data: dict[str, Any], at: datetime) -> str:
        if not _HISTORY_TYPE.fullmatch(type_):
            raise ValueError("invalid history type")
        name = f"{at.astimezone(UTC):%Y%m%d-%H%M%S-%f}-{type_}.json"
        self.write_json_atomic(self.history / name, data)
        return name

    def read_history(self) -> list[tuple[str, dict[str, Any]]]:
        if not self.history.is_dir():
            return []
        out = []
        for path in sorted(self.history.iterdir()):
            if _HISTORY.fullmatch(path.name):
                out.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
        return out
