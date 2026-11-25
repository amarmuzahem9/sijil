"""The `backup serve` loop (specs/016 FR-005, FR-008, research R5, T020)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text

from app.backup.errors import BackupBusy
from app.backup.serve import BACKUP_LOCK, BackupService
from app.models import BackupRun, BackupStatus, User
from tests.helpers.backup import seed

# 02:00 Baghdad (before the nightly time) and 03:10 Baghdad (after it).
BEFORE = datetime(2026, 11, 25, 23, 0, tzinfo=UTC)
AFTER = datetime(2026, 11, 26, 0, 10, tzinfo=UTC)


def _service(env, **over) -> BackupService:
    args = {
        "sessions": env.sessions,
        "store": env.store,
        "uploads": env.uploads,
        "recipient": env.key.recipient,
        "database_url": env.url,
        "nightly_minutes": 3 * 60,
        "min_free_bytes": 1,
        "external_dir": "/media/sijil-external",
        "app_commit": "testcommit",
    }
    return BackupService(**(args | over))


def _runs(env) -> list[BackupRun]:
    with env.sessions() as s:
        return list(s.scalars(select(BackupRun).order_by(BackupRun.created_at)))


def _request_manual(env) -> str:
    with env.sessions() as s:
        admin = s.scalar(select(User).where(User.role == "super_admin"))
        s.add(BackupRun(id="req-1", kind="manual", status="requested", requested_by=admin.id))
        s.commit()
    return "req-1"


def test_iteration_writes_the_heartbeat(backup_env) -> None:
    env = backup_env
    _service(env).iteration(BEFORE)
    with env.sessions() as s:
        status = s.get(BackupStatus, 1)
    assert status.heartbeat_at == BEFORE
    assert status.free_bytes > 0 and status.total_bytes >= status.free_bytes
    assert status.min_free_bytes == 1
    assert status.nightly_at == "03:00"
    assert status.external_dir == "/media/sijil-external"
    assert status.key_configured is True
    assert status.backup_dir_bytes is not None
    assert _runs(env) == []  # nothing due before 03:00


def test_requested_manual_run_is_taken(backup_env) -> None:
    env = backup_env
    seed(env)
    run_id = _request_manual(env)
    _service(env).iteration(BEFORE)
    (run,) = _runs(env)
    assert run.id == run_id  # the id never changes
    assert run.status == "succeeded"
    assert run.snapshot_id is not None and run.snapshot_id.endswith("-manual")
    assert run.started_at is not None and run.finished_at is not None
    assert run.total_size > 0 and run.image_count == 6
    assert run.counts["requests"] == 2
    assert env.store.list_snapshots() == [run.snapshot_id]


def test_nightly_once_per_baghdad_day(backup_env) -> None:
    env = backup_env
    seed(env)
    service = _service(env)
    service.iteration(AFTER)
    service.iteration(AFTER + timedelta(minutes=15))
    runs = _runs(env)
    assert [(r.kind, r.status) for r in runs] == [("nightly", "succeeded")]
    assert runs[0].id == runs[0].snapshot_id


def test_second_operation_is_refused_while_the_lock_is_held(backup_env) -> None:
    env = backup_env
    other = create_engine(env.url)
    with other.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": BACKUP_LOCK})
        with pytest.raises(BackupBusy):
            _service(env).run("manual")
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": BACKUP_LOCK})
    other.dispose()
    assert _runs(env) == []


def test_requested_run_waits_while_busy(backup_env) -> None:
    env = backup_env
    seed(env)
    _request_manual(env)
    other = create_engine(env.url)
    with other.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": BACKUP_LOCK})
        _service(env).iteration(BEFORE)
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": BACKUP_LOCK})
    other.dispose()
    assert [r.status for r in _runs(env)] == ["requested"]


def test_running_row_without_a_live_lock_becomes_failed_on_start(backup_env) -> None:
    env = backup_env
    with env.sessions() as s:
        s.add(BackupRun(id="stale", kind="nightly", status="running", started_at=BEFORE))
        s.commit()
    _service(env).recover()
    (run,) = _runs(env)
    assert (run.status, run.error_code) == ("failed", "internal")


def test_without_a_key_nothing_is_backed_up(backup_env) -> None:
    env = backup_env
    seed(env)
    _request_manual(env)
    _service(env, recipient="").iteration(AFTER)
    with env.sessions() as s:
        assert s.get(BackupStatus, 1).key_configured is False
    (run,) = _runs(env)
    assert (run.status, run.error_code) == ("failed", "no_key")
    assert env.store.list_snapshots(complete_only=False) == []


def test_disk_low_fails_and_is_kept_in_history(backup_env) -> None:
    env = backup_env
    service = _service(env, min_free_bytes=10**18)
    service.iteration(AFTER)
    (run,) = _runs(env)
    assert (run.kind, run.status, run.error_code) == ("nightly", "failed", "disk_low")
    failed = [data for name, data in env.store.read_history() if name.endswith("-failed.json")]
    assert len(failed) == 1 and failed[0]["error_code"] == "disk_low"
    assert env.store.list_snapshots(complete_only=False) == []


def test_retention_runs_after_success(backup_env, frozen_clock) -> None:
    env = backup_env
    old = env.store.begin_snapshot("20261001-000000-manual")  # incomplete and old
    assert old.exists()
    _service(env).iteration(AFTER)
    assert env.store.list_snapshots(complete_only=False) == [_runs(env)[0].snapshot_id]
