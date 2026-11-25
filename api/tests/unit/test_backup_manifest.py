"""Snapshot manifest (specs/016 data-model.md «manifest.json», research R4, task T008)."""

import json
from datetime import UTC, datetime

import pytest

from app.backup.manifest import Counts, DumpEntry, ImageEntry, Manifest, ManifestError
from tests.helpers.backup import image_name

_KEYS = {
    "format",
    "id",
    "kind",
    "started_at",
    "finished_at",
    "app_commit",
    "alembic_revision",
    "counts",
    "dump",
    "images",
    "missing_referenced",
    "total_size",
    "requested_by",
}


def _manifest(**over) -> Manifest:
    base = {
        "id": "20261125-000007-nightly",
        "kind": "nightly",
        "started_at": datetime(2026, 11, 25, 0, 0, 7, tzinfo=UTC),
        "finished_at": datetime(2026, 11, 25, 0, 3, 0, tzinfo=UTC),
        "app_commit": "af9155f",
        "alembic_revision": "0019",
        "counts": Counts(
            requests=3, drafts=1, legacy_subscribers=2, sas_subscribers=5, users=4, audit_entries=9
        ),
        "dump": DumpEntry(size=1234, sha256_enc="a" * 64),
        "images": [
            ImageEntry(name=image_name(1), size=10, sha256_plain="b" * 64, sha256_enc="c" * 64)
        ],
        "missing_referenced": 0,
        "total_size": 1244,
        "requested_by": None,
    }
    return Manifest(**(base | over))


def test_round_trip() -> None:
    m = _manifest()
    data = json.loads(m.to_json())
    assert set(data) == _KEYS
    assert data["format"] == 1
    assert data["started_at"] == "2026-11-25T00:00:07+00:00"
    assert set(data["counts"]) == {
        "requests",
        "drafts",
        "legacy_subscribers",
        "sas_subscribers",
        "users",
        "audit_entries",
    }
    assert set(data["images"][0]) == {"name", "size", "sha256_plain", "sha256_enc"}
    assert Manifest.from_json(m.to_json()) == m


def test_image_names_set() -> None:
    assert _manifest().image_names == {image_name(1)}


@pytest.mark.parametrize("field", sorted(_KEYS - {"requested_by"}))
def test_missing_field_refused(field) -> None:
    data = json.loads(_manifest().to_json())
    del data[field]
    with pytest.raises(ManifestError):
        Manifest.from_json(json.dumps(data))


def test_unknown_field_refused() -> None:
    data = json.loads(_manifest().to_json())
    data["phone"] = "07700000000"
    with pytest.raises(ManifestError):
        Manifest.from_json(json.dumps(data))


@pytest.mark.parametrize(
    "over",
    [
        {"kind": "weekly"},
        {"id": "../../etc-nightly"},
        {"dump": DumpEntry(size=-1, sha256_enc="a" * 64)},
        {"dump": DumpEntry(size=1, sha256_enc="xyz")},
        {"missing_referenced": -1},
        {
            "images": [
                ImageEntry(name="evil.sh", size=1, sha256_plain="b" * 64, sha256_enc="c" * 64)
            ]
        },
    ],
)
def test_invalid_values_refused(over) -> None:
    with pytest.raises(ManifestError):
        Manifest.from_json(_manifest(**over).to_json())


def test_no_environment_value_in_manifest(monkeypatch) -> None:
    markers = {
        "POSTGRES_PASSWORD": "MARKER-PG-6c1f",
        "JWT_SECRET": "MARKER-JWT-9a2e" + "x" * 32,
        "OTPIQ_API_KEY": "MARKER-OTP-77d0",
        "GOOGLE_MAPS_API_KEY": "MARKER-MAPS-31bb",
        "SUPERADMIN_PASSWORD": "MARKER-ADMIN-0e4c",
    }
    for k, v in markers.items():
        monkeypatch.setenv(k, v)
    text = _manifest().to_json()
    for v in markers.values():
        assert v not in text
