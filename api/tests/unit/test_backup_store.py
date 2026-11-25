"""Backup folder layout (specs/016 research R3, data-model.md «Files», task T007)."""

import json
import os
from datetime import UTC, datetime

import pytest

from app.backup import store
from app.backup.store import BackupStore
from tests.helpers.backup import image_name, make_age_key


@pytest.fixture
def key(tmp_path):
    return make_age_key(tmp_path)


@pytest.fixture
def bs(tmp_path):
    s = BackupStore(tmp_path / "backups")
    s.ensure_layout()
    return s


def test_layout(bs) -> None:
    for sub in ("images", "snapshots", "history"):
        path = bs.root / sub
        assert path.is_dir()
        assert (path.stat().st_mode & 0o777) == 0o700
    assert bs.key_path == bs.root / "key.age"


def test_snapshot_id_round_trip() -> None:
    started = datetime(2026, 11, 25, 0, 0, 7, tzinfo=UTC)
    sid = store.snapshot_id(started, "nightly")
    assert sid == "20261125-000007-nightly"
    assert store.parse_snapshot_id(sid) == (started, "nightly")
    assert store.parse_snapshot_id("20261125-000007-pre_deploy")[1] == "pre_deploy"


@pytest.mark.parametrize(
    "bad",
    ["20261125-000007-weekly", "2026-11-25-nightly", "../x-nightly", "20261325-000007-manual"],
)
def test_snapshot_id_refused(bad) -> None:
    with pytest.raises(ValueError):
        store.parse_snapshot_id(bad)


def test_snapshot_id_needs_utc() -> None:
    with pytest.raises(ValueError):
        store.snapshot_id(datetime(2026, 11, 25), "manual")


def test_put_image_writes_once(tmp_path, bs, key) -> None:
    src = tmp_path / image_name(1)
    src.write_bytes(b"\xff\xd8\xff synthetic jpeg")
    first = bs.put_image(src, key.recipient)
    assert first.written is True
    obj = bs.image_path(image_name(1))
    assert obj.name == image_name(1) + ".age"
    assert obj.exists()
    mtime = obj.stat().st_mtime_ns
    second = bs.put_image(src, key.recipient)
    assert second.written is False
    assert obj.stat().st_mtime_ns == mtime
    assert second.entry == first.entry
    assert first.entry.size == src.stat().st_size
    assert bs.image_entry(image_name(1)) == first.entry


@pytest.mark.parametrize(
    "bad", ["x.jpg", "../" + image_name(1), image_name(1) + ".png", "A" * 32 + ".jpg"]
)
def test_put_image_refuses_other_names(tmp_path, bs, key, bad) -> None:
    src = tmp_path / "f"
    src.write_bytes(b"x")
    with pytest.raises(ValueError):
        bs.put_image(src, key.recipient, name=bad)


def test_snapshot_is_complete_only_with_done(bs) -> None:
    sid = "20261125-000007-nightly"
    path = bs.begin_snapshot(sid)
    assert path == bs.root / "snapshots" / sid
    assert bs.list_snapshots() == []
    assert bs.list_snapshots(complete_only=False) == [sid]
    bs.mark_done(sid)
    assert bs.is_complete(sid)
    assert bs.list_snapshots() == [sid]


def test_snapshots_listed_oldest_first(bs) -> None:
    for sid in ("20261125-000007-nightly", "20261124-000007-nightly", "20261124-120000-manual"):
        bs.begin_snapshot(sid)
        bs.mark_done(sid)
    assert bs.list_snapshots() == [
        "20261124-000007-nightly",
        "20261124-120000-manual",
        "20261125-000007-nightly",
    ]


def test_history_is_atomic_and_read_back(bs) -> None:
    at = datetime(2026, 11, 25, 9, 30, tzinfo=UTC)
    name = bs.write_history("drill", {"result": "passed", "snapshot_id": "s"}, at=at)
    assert name == "20261125-093000-000000-drill.json"
    assert not list((bs.root / "history").glob("*.part"))
    assert json.loads((bs.root / "history" / name).read_text()) == {
        "result": "passed",
        "snapshot_id": "s",
    }
    assert bs.read_history() == [(name, {"result": "passed", "snapshot_id": "s"})]


def test_history_ignores_temp_and_foreign_files(bs) -> None:
    (bs.root / "history" / "x.json.part").write_text("{")
    (bs.root / "history" / "notes.txt").write_text("hi")
    assert bs.read_history() == []


def test_write_json_atomic_replaces(bs) -> None:
    target = bs.root / "snapshots" / "m.json"
    bs.write_json_atomic(target, {"a": 1})
    bs.write_json_atomic(target, {"a": 2})
    assert json.loads(target.read_text()) == {"a": 2}
    assert (target.stat().st_mode & 0o777) == 0o600
    assert os.listdir(target.parent) == ["m.json"]
