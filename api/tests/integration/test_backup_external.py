"""The weekly copy to the external drive (specs/016 US4, FR-007, research R10, T055).

The drive is plugged in by hand (owner decision Q2-B). Nothing on it is ever removed or
overwritten; every copied file is re-read and checked; DONE comes last.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.backup import external, restore
from app.backup.external import MARKER, ExternalCopyFailed
from app.backup.snapshot import SnapshotConfig, take_snapshot
from app.backup.store import BackupStore
from tests.helpers.backup import new_image_name, seed

AT = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)


def _cfg(env) -> SnapshotConfig:
    return SnapshotConfig(
        store=env.store,
        uploads=env.uploads,
        recipient=env.key.recipient,
        database_url=env.url,
        app_commit="testcommit",
    )


@pytest.fixture
def drive(backup_env):
    env = backup_env
    env.store.key_path.write_text("-----BEGIN AGE ENCRYPTED FILE-----\nsynthetic\n")
    target = env.tmp / "drive"
    target.mkdir()
    (target / MARKER).write_text("sijil external drive\n")
    return env, target


def _history(env, suffix: str) -> list[dict]:
    return [d for n, d in env.store.read_history() if n.endswith(suffix)]


def test_copies_the_latest_snapshot_with_its_objects_and_the_key(drive) -> None:
    env, target = drive
    seed(env)
    manifest = take_snapshot(_cfg(env), "nightly")
    result = external.copy(env.store, target, at=AT)
    assert result.snapshot_id == manifest.id
    copy = BackupStore(target)
    assert copy.list_snapshots() == [manifest.id]
    assert restore.verify(copy, manifest.id) == manifest  # every hash checks out on the drive
    assert copy.key_path.read_bytes() == env.store.key_path.read_bytes()
    assert result.objects_new == len(manifest.images)
    assert result.bytes_copied > 0
    (record,) = _history(env, "-external_copy.json")
    assert record["result"] == "succeeded" and record["snapshot_id"] == manifest.id
    assert record["details"]["objects_new"] == len(manifest.images)


def test_second_copy_reuses_objects_and_keeps_everything(drive, frozen_clock) -> None:
    env, target = drive
    seed(env)
    first = take_snapshot(_cfg(env), "nightly")
    external.copy(env.store, target, at=AT)
    copy = BackupStore(target)
    mtimes = {n: copy.image_path(n).stat().st_mtime_ns for n in first.image_names}
    (target / "owner-notes.txt").write_text("kept")  # anything else on the drive stays

    new = new_image_name()
    (env.uploads / new).write_bytes(b"\xff\xd8\xff a new synthetic image")
    frozen_clock.advance(timedelta(days=7))
    second = take_snapshot(_cfg(env), "nightly")
    result = external.copy(env.store, target, at=AT + timedelta(days=7))

    assert result.snapshot_id == second.id
    assert result.objects_new == 1
    assert copy.list_snapshots() == [first.id, second.id]  # the older copy is kept
    assert {n: copy.image_path(n).stat().st_mtime_ns for n in first.image_names} == mtimes
    assert (target / "owner-notes.txt").read_text() == "kept"
    assert restore.verify(copy, first.id) and restore.verify(copy, second.id)


def test_a_snapshot_already_on_the_drive_is_not_rewritten(drive) -> None:
    env, target = drive
    seed(env)
    take_snapshot(_cfg(env), "nightly")
    external.copy(env.store, target, at=AT)
    again = external.copy(env.store, target, at=AT + timedelta(hours=1))
    assert again.objects_new == 0 and again.already_there is True


def test_refused_without_the_marker(drive) -> None:
    env, target = drive
    seed(env)
    take_snapshot(_cfg(env), "nightly")
    (target / MARKER).unlink()
    with pytest.raises(ExternalCopyFailed) as info:
        external.copy(env.store, target, at=AT)
    assert info.value.code == "not_marked"
    assert sorted(p.name for p in target.iterdir()) == []
    (record,) = _history(env, "-external_copy.json")
    assert record["result"] == "failed" and record["details"]["reason"] == "not_marked"


def test_refused_before_writing_when_the_drive_is_full(drive, monkeypatch) -> None:
    env, target = drive
    seed(env)
    take_snapshot(_cfg(env), "nightly")

    class Usage:
        total, used, free = 10**9, 10**9 - 10, 10

    monkeypatch.setattr(external.shutil, "disk_usage", lambda _: Usage())
    with pytest.raises(ExternalCopyFailed) as info:
        external.copy(env.store, target, at=AT)
    assert info.value.code == "no_space"
    assert sorted(p.name for p in target.iterdir()) == [MARKER]


def test_a_bad_write_is_caught_and_not_marked_done(drive, monkeypatch) -> None:
    env, target = drive
    seed(env)
    manifest = take_snapshot(_cfg(env), "nightly")
    real = external._copy_file

    def corrupting(src, dst):
        real(src, dst)
        if dst.name.endswith(".jpg.age"):
            dst.write_bytes(dst.read_bytes()[:-1])

    monkeypatch.setattr(external, "_copy_file", corrupting)
    with pytest.raises(ExternalCopyFailed) as info:
        external.copy(env.store, target, at=AT)
    assert info.value.code == "verify_failed"
    assert not (target / "snapshots" / manifest.id / "DONE").exists()


def test_a_different_key_on_the_drive_is_refused(drive) -> None:
    env, target = drive
    seed(env)
    take_snapshot(_cfg(env), "nightly")
    (target / "key.age").write_text("another key")
    with pytest.raises(ExternalCopyFailed) as info:
        external.copy(env.store, target, at=AT)
    assert info.value.code == "key_mismatch"
    assert (target / "key.age").read_text() == "another key"  # never overwritten


def test_nothing_to_copy_without_a_snapshot(drive) -> None:
    env, target = drive
    with pytest.raises(ExternalCopyFailed) as info:
        external.copy(env.store, target, at=AT)
    assert info.value.code == "no_snapshot"


def test_record_holds_no_path_or_personal_data(drive) -> None:
    env, target = drive
    seed(env)
    take_snapshot(_cfg(env), "nightly")
    external.copy(env.store, target, at=AT)
    text = json.dumps(_history(env, "-external_copy.json"), ensure_ascii=False)
    assert str(target) not in text
    for personal in ("تجربة", "0790000"):
        assert personal not in text


def test_cli_external_copy_exit_codes(drive, monkeypatch, capsys) -> None:
    from app.backup import __main__ as cli
    from app.config import get_settings

    env, target = drive
    monkeypatch.setenv("BACKUP_DIR", str(env.store.root))
    get_settings.cache_clear()
    try:
        assert cli.main(["external-copy", "--target", str(target)]) == 5  # no snapshot yet
        seed(env)
        take_snapshot(_cfg(env), "nightly")
        assert cli.main(["external-copy", "--target", str(target)]) == 0
        assert "يمكن فصل الهارد" not in capsys.readouterr().out  # the shell says it after the drill
    finally:
        get_settings.cache_clear()
