"""Backup warnings on the admin home, main admin only (specs/016 FR-017, contracts/api.md, T045)."""

from datetime import UTC, datetime, timedelta

from app.models import BackupRun, BackupStatus
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)


def _failed_state(db) -> None:
    db.add(BackupStatus(id=1, heartbeat_at=NOW, nightly_at="03:00", key_configured=True))
    db.add(
        BackupRun(
            id="bad",
            kind="nightly",
            status="failed",
            error_code="disk_low",
            started_at=NOW - timedelta(minutes=5),
            finished_at=NOW - timedelta(minutes=4),
        )
    )
    db.flush()


def test_main_admin_sees_the_warnings(client, db, make_user, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _failed_state(db)
    body = client.get("/api/admin/home", headers=headers_for(client, make_user("super_admin")))
    assert body.status_code == 200
    warnings = body.json()["backup_warnings"]
    assert "last_failed" in warnings


def test_other_admins_get_an_empty_list(client, db, make_user, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _failed_state(db)
    h = headers_for(client, admin_with(make_user, "review", "settings"))
    assert client.get("/api/admin/home", headers=h).json()["backup_warnings"] == []
