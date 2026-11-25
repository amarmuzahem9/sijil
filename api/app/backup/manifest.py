"""Snapshot manifest (specs/016 data-model.md «manifest.json», research R4).

Plaintext on purpose: retention, verification without the passphrase and the admin page need it.
It holds aggregate counts, random image file names and hashes only, never personal data.
"""

import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any

FORMAT = 1
KINDS = ("nightly", "manual", "pre_deploy", "pre_restore")
IMAGE_NAME = re.compile(r"[0-9a-f]{32}\.jpg")
SNAPSHOT_ID = re.compile(r"\d{8}-\d{6}-(nightly|manual|pre_deploy|pre_restore)")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ManifestError(ValueError):
    """A manifest that is missing a field, has an unknown one, or holds an invalid value."""


@dataclass(frozen=True)
class Counts:
    requests: int
    drafts: int
    legacy_subscribers: int
    sas_subscribers: int
    users: int
    audit_entries: int


@dataclass(frozen=True)
class DumpEntry:
    size: int
    sha256_enc: str


@dataclass(frozen=True)
class ImageEntry:
    name: str
    size: int
    sha256_plain: str
    sha256_enc: str


@dataclass(frozen=True)
class Manifest:
    id: str
    kind: str
    started_at: datetime
    finished_at: datetime
    app_commit: str
    alembic_revision: str
    counts: Counts
    dump: DumpEntry
    images: list[ImageEntry] = field(default_factory=list)
    missing_referenced: int = 0
    total_size: int = 0
    requested_by: int | None = None

    @property
    def image_names(self) -> set[str]:
        return {image.name for image in self.images}

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat()
        return {"format": FORMAT, **data}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestError("not JSON") from exc
        if not isinstance(data, dict):
            raise ManifestError("not an object")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        expected = {f.name for f in fields(cls)} | {"format"}
        if set(data) - expected:
            raise ManifestError("unknown field")
        if set(data) | {"requested_by"} != expected:
            raise ManifestError("missing field")
        if data["format"] != FORMAT:
            raise ManifestError("unsupported format")
        try:
            manifest = cls(
                id=data["id"],
                kind=data["kind"],
                started_at=datetime.fromisoformat(data["started_at"]),
                finished_at=datetime.fromisoformat(data["finished_at"]),
                app_commit=data["app_commit"],
                alembic_revision=data["alembic_revision"],
                counts=_build(Counts, data["counts"]),
                dump=_build(DumpEntry, data["dump"]),
                images=[_build(ImageEntry, image) for image in data["images"]],
                missing_referenced=data["missing_referenced"],
                total_size=data["total_size"],
                requested_by=data.get("requested_by"),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ManifestError("invalid value") from exc
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if not (isinstance(self.id, str) and SNAPSHOT_ID.fullmatch(self.id)):
            raise ManifestError("invalid id")
        if self.kind not in KINDS or not self.id.endswith("-" + self.kind):
            raise ManifestError("invalid kind")
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ManifestError("times must be UTC")
        if not all(_count(v) for v in asdict(self.counts).values()):
            raise ManifestError("invalid counts")
        if not (_count(self.dump.size) and _sha(self.dump.sha256_enc)):
            raise ManifestError("invalid dump entry")
        for image in self.images:
            if not (
                isinstance(image.name, str)
                and IMAGE_NAME.fullmatch(image.name)
                and _count(image.size)
                and _sha(image.sha256_plain)
                and _sha(image.sha256_enc)
            ):
                raise ManifestError("invalid image entry")
        if not (_count(self.missing_referenced) and _count(self.total_size)):
            raise ManifestError("invalid totals")
        if self.requested_by is not None and not _count(self.requested_by):
            raise ManifestError("invalid requested_by")


def _build(cls, data: Any):
    if not isinstance(data, dict) or set(data) != {f.name for f in fields(cls)}:
        raise ManifestError(f"invalid {cls.__name__}")
    return cls(**data)


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))
