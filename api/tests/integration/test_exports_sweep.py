"""Export files are removed 24 h after they are ready and are never in a backup (docs/system.md
v1.25 §11, §15; specs/019 FR-013, SC-006; research R10). Synthetic data only.
"""

import uuid
from datetime import timedelta

import pytest

from app.backup import snapshot
from app.config import get_settings
from app.core.timeutil import utc_now
from app.models import Export
from app.services import export_service


@pytest.fixture
def admin(make_user):
    return make_user("super_admin")


def _export(db, exports_dir, admin, *, state: str, ready_ago: timedelta | None = None) -> Export:
    now = utc_now()
    export = Export(
        id=uuid.uuid4(),
        requester_id=admin.id,
        filters={"period": "month", "date_kind": "submitted"},
        include_identity=False,
        state=state,
        created_at=now - (ready_ago or timedelta()),
    )
    if state == "ready":
        export.ready_at = now - ready_ago
        export.expires_at = export.ready_at + export_service.KEEP_FOR
        export.row_count = 1
    if state == "failed":
        export.error_code = "build_failed"
    db.add(export)
    db.flush()
    folder = exports_dir / str(export.id)
    folder.mkdir()
    (folder / "requests.xlsx").write_bytes(b"synthetic")
    return export


def test_keep_for_is_24_hours() -> None:
    assert export_service.KEEP_FOR == timedelta(hours=24)


def test_an_expired_export_is_removed(db, exports_dir, admin, frozen_clock) -> None:
    old = _export(db, exports_dir, admin, state="ready", ready_ago=timedelta(hours=24, seconds=1))
    fresh = _export(db, exports_dir, admin, state="ready", ready_ago=timedelta(hours=23))
    removed = export_service.sweep_expired(session=db)
    assert removed == 1
    db.refresh(old)
    db.refresh(fresh)
    assert old.state == "removed" and old.removed_at is not None
    assert old.ready_at is not None  # a removed row keeps its history (data-model.md)
    assert not (exports_dir / str(old.id)).exists()
    assert fresh.state == "ready"
    assert (exports_dir / str(fresh.id) / "requests.xlsx").exists()


def test_a_failed_export_folder_is_removed(db, exports_dir, admin, frozen_clock) -> None:
    failed = _export(db, exports_dir, admin, state="failed")
    export_service.sweep_expired(session=db)
    db.refresh(failed)
    # The folder goes at once; the row stays «فشل التجهيز» for its owner for 24 hours.
    assert not (exports_dir / str(failed.id)).exists()
    assert failed.state == "failed"
    frozen_clock.advance(export_service.KEEP_FOR + timedelta(seconds=1))
    export_service.sweep_expired(session=db)
    db.refresh(failed)
    assert failed.state == "removed" and failed.removed_at is not None


def test_a_preparing_export_is_left_alone(db, exports_dir, admin) -> None:
    preparing = _export(db, exports_dir, admin, state="preparing")
    export_service.sweep_expired(session=db)
    db.refresh(preparing)
    assert preparing.state == "preparing"


def test_a_stray_folder_without_a_row_is_removed(db, exports_dir) -> None:
    stray = exports_dir / str(uuid.uuid4())
    stray.mkdir()
    (stray / "requests.xlsx").write_bytes(b"synthetic")
    export_service.sweep_expired(session=db)
    assert not stray.exists()


def test_a_missing_exports_folder_is_not_an_error(db, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "exports_dir", str(tmp_path / "absent"))
    assert export_service.sweep_expired(session=db) == 0


def test_exports_are_never_backed_up(db, exports_dir, admin, tmp_path, monkeypatch) -> None:
    """The backup copies image-named files from the uploads folder only (specs/016 R3)."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(get_settings(), "uploads_dir", str(uploads))
    export = _export(db, exports_dir, admin, state="ready", ready_ago=timedelta(hours=1))
    assert str(exports_dir) not in str(uploads)
    stored = snapshot.stored_files(uploads)
    assert all(str(export.id) not in str(p) for p in stored)
    assert snapshot.stored_files(exports_dir) == []
    assert snapshot.stored_files(exports_dir / str(export.id)) == []
