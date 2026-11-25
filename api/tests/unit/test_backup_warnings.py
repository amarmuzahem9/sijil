"""Warnings for the main admin (specs/016 FR-017, research R12, contracts/api.md, T044)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import BackupEvent, BackupRun, BackupStatus
from app.services import backup_warnings

NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)
GB = 1024**3


@pytest.fixture
def healthy(db, frozen_clock):
    """A healthy state: heartbeat now, key set, room on disk, a backup an hour ago, a drill and
    an external copy two days ago."""
    frozen_clock.set(NOW)
    db.add(
        BackupStatus(
            id=1,
            heartbeat_at=NOW - timedelta(seconds=20),
            free_bytes=50 * GB,
            total_bytes=100 * GB,
            min_free_bytes=2 * GB,
            nightly_at="03:00",
            external_dir="/media/sijil-external",
            backup_dir_bytes=GB,
            key_configured=True,
        )
    )
    _run(db, "ok-1", "succeeded", NOW - timedelta(hours=1))
    _event(db, "drill", "passed", NOW - timedelta(days=2))
    _event(db, "external_copy", "succeeded", NOW - timedelta(days=2))
    db.flush()
    return db


def _run(db, run_id: str, status: str, finished: datetime, error: str | None = None) -> None:
    db.add(
        BackupRun(
            id=run_id,
            snapshot_id=run_id if status == "succeeded" else None,
            kind="nightly",
            status=status,
            error_code=error,
            started_at=finished - timedelta(minutes=2),
            finished_at=finished,
            created_at=finished - timedelta(minutes=2),
        )
    )
    db.flush()


def _event(db, type_: str, result: str, at: datetime) -> None:
    db.add(BackupEvent(id=f"{at:%Y%m%d-%H%M%S-%f}-{type_}.json", type=type_, at=at, result=result))
    db.flush()


def _warnings(db) -> list[str]:
    return backup_warnings.compute(db, NOW)


def test_no_warning_when_healthy(healthy) -> None:
    assert _warnings(healthy) == []


def test_last_failed(healthy) -> None:
    _run(healthy, "bad-1", "failed", NOW - timedelta(minutes=5), error="disk_low")
    assert _warnings(healthy) == ["last_failed"]


def test_last_failed_clears_after_a_success(healthy) -> None:
    _run(healthy, "bad-1", "failed", NOW - timedelta(minutes=30), error="disk_low")
    _run(healthy, "ok-2", "succeeded", NOW - timedelta(minutes=5))
    assert _warnings(healthy) == []


def test_removed_runs_are_ignored(healthy) -> None:
    _run(healthy, "old", "removed", NOW - timedelta(minutes=1))
    assert _warnings(healthy) == []


def test_no_recent_backup_after_36_hours(healthy) -> None:
    healthy.get(BackupRun, "ok-1").finished_at = NOW - timedelta(hours=36, minutes=1)
    assert _warnings(healthy) == ["no_recent_backup"]
    healthy.get(BackupRun, "ok-1").finished_at = NOW - timedelta(hours=35, minutes=59)
    assert _warnings(healthy) == []


def test_no_backup_at_all(db, frozen_clock) -> None:
    frozen_clock.set(NOW)
    db.add(
        BackupStatus(
            id=1,
            heartbeat_at=NOW,
            nightly_at="03:00",
            key_configured=True,
            free_bytes=50 * GB,
            min_free_bytes=2 * GB,
        )
    )
    db.flush()
    assert "no_recent_backup" in _warnings(db)


def test_external_overdue_after_8_days_or_never(healthy) -> None:
    event = healthy.query(BackupEvent).filter_by(type="external_copy").one()
    event.at = NOW - timedelta(days=8, minutes=1)
    assert _warnings(healthy) == ["external_overdue"]
    healthy.delete(event)
    healthy.flush()
    assert _warnings(healthy) == ["external_overdue"]


def test_failed_external_copy_does_not_count(healthy) -> None:
    healthy.query(BackupEvent).filter_by(type="external_copy").one().at = NOW - timedelta(days=9)
    _event(healthy, "external_copy", "failed", NOW - timedelta(hours=1))
    assert _warnings(healthy) == ["external_overdue"]


def test_drill_failed(healthy) -> None:
    _event(healthy, "drill", "failed", NOW - timedelta(hours=1))
    assert _warnings(healthy) == ["drill_failed_or_overdue"]


def test_drill_overdue(healthy) -> None:
    healthy.query(BackupEvent).filter_by(type="drill").one().at = NOW - timedelta(days=8, hours=1)
    assert _warnings(healthy) == ["drill_failed_or_overdue"]


def test_disk_low_before_backups_are_refused(healthy) -> None:
    status = healthy.get(BackupStatus, 1)
    status.free_bytes = 4 * GB - 1  # under twice the margin
    assert _warnings(healthy) == ["disk_low"]
    status.free_bytes = 4 * GB
    assert _warnings(healthy) == []


def test_service_down_after_10_minutes(healthy) -> None:
    healthy.get(BackupStatus, 1).heartbeat_at = NOW - timedelta(minutes=10, seconds=1)
    assert _warnings(healthy) == ["service_down"]


def test_service_down_without_any_status(db, frozen_clock) -> None:
    frozen_clock.set(NOW)
    assert _warnings(db)[0] == "service_down"


def test_no_key(healthy) -> None:
    healthy.get(BackupStatus, 1).key_configured = False
    assert _warnings(healthy) == ["no_key"]


def test_order_is_fixed(healthy) -> None:
    status = healthy.get(BackupStatus, 1)
    status.heartbeat_at = NOW - timedelta(hours=1)
    status.free_bytes = GB
    _run(healthy, "bad-1", "failed", NOW - timedelta(minutes=5), error="internal")
    healthy.query(BackupEvent).delete()
    healthy.flush()
    assert _warnings(healthy) == [
        "service_down",
        "last_failed",
        "disk_low",
        "drill_failed_or_overdue",
        "external_overdue",
    ]


def test_texts_are_arabic_for_every_code() -> None:
    assert set(backup_warnings.TEXTS) == set(backup_warnings.CODES)
    assert backup_warnings.TEXTS["last_failed"] == "فشل آخر نسخ احتياطي"
