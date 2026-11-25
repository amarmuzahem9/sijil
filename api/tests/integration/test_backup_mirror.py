"""The database mirrors the backup files (specs/016 research R8, T021).

A restore takes the database back in time; the mirror must come back from the files, so the
page still lists every later backup, failure and event.
"""

import shutil
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.backup import mirror
from app.backup.snapshot import SnapshotConfig, take_snapshot
from app.models import BackupEvent, BackupRun, User
from tests.helpers.backup import seed

AT = datetime(2026, 11, 25, 9, 30, tzinfo=UTC)


def _cfg(env) -> SnapshotConfig:
    return SnapshotConfig(
        store=env.store,
        uploads=env.uploads,
        recipient=env.key.recipient,
        database_url=env.url,
        app_commit="testcommit",
    )


def _state(env):
    with env.sessions() as s:
        runs = [
            (r.id, r.snapshot_id, r.kind, r.status, r.error_code, r.total_size, r.image_count)
            for r in s.scalars(select(BackupRun).order_by(BackupRun.id))
        ]
        events = [
            (e.id, e.type, e.result, e.snapshot_id, e.details)
            for e in s.scalars(select(BackupEvent).order_by(BackupEvent.id))
        ]
    return runs, events


def _prepare(env, frozen_clock):
    seed(env)
    first = take_snapshot(_cfg(env), "nightly")
    frozen_clock.advance(timedelta(hours=1))
    second = take_snapshot(_cfg(env), "manual")
    env.store.write_history(
        "drill",
        {"result": "passed", "snapshot_id": first.id, "details": {"requests": 2}},
        at=AT,
    )
    env.store.write_history(
        "failed",
        {
            "run_id": "req-9",
            "kind": "manual",
            "error_code": "disk_low",
            "started_at": AT.isoformat(),
            "finished_at": AT.isoformat(),
            "requested_by": None,
        },
        at=AT + timedelta(minutes=1),
    )
    return first, second


def test_rows_are_rebuilt_from_the_files(backup_env, frozen_clock) -> None:
    env = backup_env
    first, second = _prepare(env, frozen_clock)
    with env.sessions() as s:
        mirror.sync(s, env.store)
        s.commit()
    runs, events = _state(env)
    assert {(r[1], r[2], r[3]) for r in runs} == {
        (first.id, "nightly", "succeeded"),
        (second.id, "manual", "succeeded"),
        (None, "manual", "failed"),
    }
    failed = next(r for r in runs if r[3] == "failed")
    assert (failed[0], failed[4]) == ("req-9", "disk_low")
    ok = next(r for r in runs if r[1] == first.id)
    assert ok[5] == first.total_size and ok[6] == len(first.images)
    assert [(e[1], e[2], e[3]) for e in events] == [("drill", "passed", first.id)]
    assert events[0][4] == {"requests": 2}


def test_vanished_folder_becomes_removed(backup_env, frozen_clock) -> None:
    env = backup_env
    first, second = _prepare(env, frozen_clock)
    with env.sessions() as s:
        mirror.sync(s, env.store)
        s.commit()
    shutil.rmtree(env.store.snapshot_dir(first.id))
    with env.sessions() as s:
        mirror.sync(s, env.store)
        s.commit()
        row = s.scalar(select(BackupRun).where(BackupRun.snapshot_id == first.id))
        assert row.status == "removed" and row.removed_at is not None


def test_deleting_all_rows_then_syncing_gives_them_back(backup_env, frozen_clock) -> None:
    env = backup_env
    _prepare(env, frozen_clock)
    with env.sessions() as s:
        mirror.sync(s, env.store)
        s.commit()
    before = _state(env)
    with env.sessions() as s:
        s.execute(delete(BackupRun))
        s.execute(delete(BackupEvent))
        s.commit()
        mirror.sync(s, env.store)
        s.commit()
    assert _state(env) == before


def test_manual_request_keeps_its_id(backup_env, frozen_clock) -> None:
    env = backup_env
    seed(env)
    manifest = take_snapshot(_cfg(env), "manual")
    with env.sessions() as s:
        admin = s.scalar(select(User).where(User.role == "super_admin"))
        s.add(
            BackupRun(
                id="req-1",
                snapshot_id=manifest.id,
                kind="manual",
                status="succeeded",
                requested_by=admin.id,
            )
        )
        s.commit()
        mirror.sync(s, env.store)
        s.commit()
        rows = list(s.scalars(select(BackupRun)))
    assert [(r.id, r.snapshot_id, r.requested_by is not None) for r in rows] == [
        ("req-1", manifest.id, True)
    ]


def test_requested_by_of_an_unknown_user_is_dropped(backup_env, frozen_clock) -> None:
    # After a restore to an older moment the requesting admin may not exist yet.
    env = backup_env
    seed(env)
    manifest = take_snapshot(_cfg(env), "manual", requested_by=999_999)
    with env.sessions() as s:
        mirror.sync(s, env.store)
        s.commit()
        row = s.scalar(select(BackupRun).where(BackupRun.snapshot_id == manifest.id))
    assert row.requested_by is None


def test_a_row_with_the_same_id_is_reused_not_inserted_again(backup_env, frozen_clock) -> None:
    # After a restore, the restored database holds the row of that very backup (it was taken
    # while the backup ran); it may have lost its snapshot_id. Sync must reuse it.
    env = backup_env
    seed(env)
    manifest = take_snapshot(_cfg(env), "manual")
    with env.sessions() as s:
        s.add(BackupRun(id=manifest.id, kind="manual", status="failed", error_code="internal"))
        s.commit()
        mirror.sync(s, env.store)
        s.commit()
        (row,) = list(s.scalars(select(BackupRun)))
    assert (row.id, row.snapshot_id, row.status, row.error_code) == (
        manifest.id,
        manifest.id,
        "succeeded",
        None,
    )
