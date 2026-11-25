"""The backup page API, main admin only (specs/016 FR-016, contracts/api.md, T043)."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.access import ADMIN_PERMISSIONS
from app.models import AuditLog, BackupEvent, BackupRun, BackupStatus
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 27, 9, 0, tzinfo=UTC)
GB = 1024**3


@pytest.fixture
def main_admin(make_user):
    return make_user("super_admin")


@pytest.fixture
def state(db, frozen_clock):
    frozen_clock.set(NOW)
    db.add(
        BackupStatus(
            id=1,
            heartbeat_at=NOW - timedelta(seconds=10),
            free_bytes=50 * GB,
            total_bytes=100 * GB,
            min_free_bytes=2 * GB,
            nightly_at="03:00",
            external_dir="/media/sijil-external",
            backup_dir_bytes=3 * GB,
            key_configured=True,
        )
    )
    for i, (status, removed) in enumerate(
        [("succeeded", False), ("failed", False), ("removed", True), ("succeeded", False)]
    ):
        at = NOW - timedelta(days=3 - i)
        sid = f"{at:%Y%m%d-%H%M%S}-nightly"
        db.add(
            BackupRun(
                id=sid if status != "failed" else f"run-{i}",
                snapshot_id=sid if status != "failed" else None,
                kind="nightly",
                status=status,
                error_code="disk_low" if status == "failed" else None,
                started_at=at,
                finished_at=at + timedelta(minutes=2),
                total_size=1000 + i,
                image_count=10,
                counts={"requests": 5, "legacy_subscribers": 1, "sas_subscribers": 2, "users": 3},
                removed_at=NOW if removed else None,
                created_at=at,
            )
        )
    db.add(
        BackupEvent(
            id="d.json",
            type="drill",
            at=NOW - timedelta(days=1),
            result="passed",
            snapshot_id="s1",
            details={"source": "external", "reason": None},
        )
    )
    db.add(
        BackupEvent(
            id="e.json",
            type="external_copy",
            at=NOW - timedelta(days=1),
            result="succeeded",
            snapshot_id="s1",
        )
    )
    db.add(
        BackupEvent(
            id="p.json",
            type="deploy",
            at=NOW - timedelta(days=2),
            result="succeeded",
            details={"mode": "staging", "new_commit": "abc1234"},
        )
    )
    db.flush()
    return db


def test_page_shape(client, state, main_admin) -> None:
    res = client.get("/api/admin/backup", headers=headers_for(client, main_admin))
    assert res.status_code == 200, res.json()
    body = res.json()
    assert set(body) == {
        "status",
        "running",
        "runs",
        "last_external",
        "last_drill",
        "deploys",
        "warnings",
    }
    assert body["status"]["service_ok"] is True
    assert body["status"]["external_dir"] == "/media/sijil-external"
    assert body["status"]["key_configured"] is True
    assert body["status"]["nightly_at"] == "03:00"
    assert body["running"] is None
    # Newest first, removed excluded.
    assert [r["status"] for r in body["runs"]] == ["succeeded", "failed", "succeeded"]
    assert body["runs"][1]["error_code"] == "disk_low"
    assert body["runs"][0]["counts"]["requests"] == 5
    assert body["last_drill"]["result"] == "passed" and body["last_drill"]["source"] == "external"
    assert body["last_external"]["result"] == "succeeded"
    assert body["deploys"] == [
        {
            "at": body["deploys"][0]["at"],
            "result": "succeeded",
            "mode": "staging",
            "commit": "abc1234",
        }
    ]
    assert body["warnings"] == []


def test_running_run_is_shown_apart(client, state, main_admin) -> None:
    state.add(BackupRun(id="req-x", kind="manual", status="running", started_at=NOW))
    state.flush()
    body = client.get("/api/admin/backup", headers=headers_for(client, main_admin)).json()
    assert body["running"]["id"] == "req-x" and body["running"]["kind"] == "manual"
    assert all(r["id"] != "req-x" for r in body["runs"])


def test_manual_backup_is_requested_and_audited(client, state, main_admin) -> None:
    h = headers_for(client, main_admin)
    res = client.post("/api/admin/backup/run", headers=h)
    assert res.status_code == 202, res.json()
    run_id = res.json()["id"]
    row = state.get(BackupRun, run_id)
    assert (row.kind, row.status, row.requested_by) == ("manual", "requested", main_admin.id)
    entry = state.scalar(select(AuditLog).where(AuditLog.action == "backup.manual_requested"))
    assert entry.actor_id == main_admin.id and entry.entity_id == run_id

    again = client.post("/api/admin/backup/run", headers=h)
    assert again.status_code == 409
    assert again.json()["code"] == "backup_busy"
    assert again.json()["message"] == "يوجد نسخ جارٍ الآن"


def test_manual_backup_refused_while_the_service_is_down(client, state, main_admin) -> None:
    state.get(BackupStatus, 1).heartbeat_at = NOW - timedelta(minutes=11)
    state.flush()
    res = client.post("/api/admin/backup/run", headers=headers_for(client, main_admin))
    assert res.status_code == 503
    assert res.json()["code"] == "backup_service_down"
    assert state.scalar(select(BackupRun).where(BackupRun.status == "requested")) is None


def test_added_admin_with_every_permission_is_refused(client, state, make_user) -> None:
    h = headers_for(client, admin_with(make_user, *ADMIN_PERMISSIONS))
    assert client.get("/api/admin/backup", headers=h).status_code == 403
    assert client.post("/api/admin/backup/run", headers=h).status_code == 403


def test_marketer_is_refused(client, state, make_user) -> None:
    h = headers_for(client, make_user("marketer"))
    assert client.get("/api/admin/backup", headers=h).status_code == 403
    assert client.post("/api/admin/backup/run", headers=h).status_code == 403


def test_no_personal_data_in_the_body(client, state, main_admin) -> None:
    text = json.dumps(
        client.get("/api/admin/backup", headers=headers_for(client, main_admin)).json()
    )
    for word in ("phone", "name", "national", "family", "password", "key", "username"):
        assert f'"{word}' not in text.replace('"key_configured"', ""), word
