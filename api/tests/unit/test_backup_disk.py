"""Disk guard before a backup (specs/016 FR-009, research R6, T018)."""

import pytest

from app.backup import retention
from app.backup.errors import SnapshotFailed
from app.backup.store import BackupStore
from tests.helpers.backup import image_name, make_age_key

GB = 1024**3


def test_estimate_is_new_images_plus_last_dump(tmp_path) -> None:
    key = make_age_key(tmp_path)
    store = BackupStore(tmp_path / "b")
    store.ensure_layout()
    uploads = tmp_path / "u"
    uploads.mkdir()
    (uploads / image_name(1)).write_bytes(b"a" * 1000)  # already stored
    store.put_image(uploads / image_name(1), key.recipient)
    (uploads / image_name(2)).write_bytes(b"b" * 3000)  # new
    (uploads / "x.jpg.part").write_bytes(b"c" * 99999)  # an upload in progress: ignored
    assert retention.estimate_bytes(store, uploads, last_dump_size=500) == 3000 + 500


def test_estimate_without_any_snapshot(tmp_path) -> None:
    store = BackupStore(tmp_path / "b")
    store.ensure_layout()
    uploads = tmp_path / "u"
    uploads.mkdir()
    assert retention.estimate_bytes(store, uploads, last_dump_size=0) == 0


def test_refused_when_free_space_would_drop_under_the_margin() -> None:
    with pytest.raises(SnapshotFailed) as info:
        retention.check_disk(free_bytes=3 * GB, estimate=int(1.5 * GB), min_free_gb=2)
    assert info.value.code == "disk_low"


def test_accepted_with_room_left() -> None:
    retention.check_disk(free_bytes=5 * GB, estimate=2 * GB, min_free_gb=2)
    retention.check_disk(free_bytes=4 * GB, estimate=2 * GB, min_free_gb=2)  # exactly the margin
