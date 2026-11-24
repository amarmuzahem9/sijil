"""Marketer notifications through the API (specs/012 US2, US4: FR-016 to FR-024; contracts/api.md).
Synthetic data only."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Notification
from app.services import notification_service
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for, pending_request
from tests.helpers.submit import complete_draft, make_catalog, marketer_headers, submit

LIST = "/api/notifications"


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    get_otp_sender().outbox.clear()
    return tmp_path


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, marketer):
    return marketer_headers(client, marketer)


def _count(client, h) -> int:
    res = client.get(f"{LIST}/unread-count", headers=h)
    assert res.status_code == 200, res.json()
    return res.json()["count"]


def test_auto_acceptance_adds_no_notification(client, db, make_user, marketer, h) -> None:
    catalog = make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))
    res = submit(client, h, complete_draft(client, h, catalog))
    assert (res.status_code, res.json()["status"]) == (201, "approved")
    assert db.scalars(select(Notification)).all() == []
    assert _count(client, h) == 0


def test_accept_then_list_count_read(client, db, make_user, marketer, h) -> None:
    request = pending_request(db, marketer, [("numbers_edited", None, {})])
    admin = headers_for(client, admin_with(make_user, "review"))
    res = client.post(f"/api/admin/requests/{request.id}/accept", json={}, headers=admin)
    assert res.status_code == 200
    assert _count(client, h) == 1

    res = client.get(LIST, headers=h)
    assert res.status_code == 200
    body = res.json()
    assert body["next_before"] is None
    (item,) = body["items"]
    assert item["kind"] == "approved"
    assert item["request_id"] == request.id
    assert item["number_label"] == request.number_label
    assert item["full_name"] == request.full_name
    assert (item["deleted"], item["reason_label"], item["read_at"]) == (False, None, None)

    assert client.post(f"{LIST}/{item['id']}/read", headers=h).status_code == 204
    assert _count(client, h) == 0
    assert client.get(LIST, headers=h).json()["items"][0]["read_at"] is not None


def test_reject_shows_the_label_never_the_note(client, db, make_user, marketer, h) -> None:
    request = pending_request(db, marketer, [("numbers_edited", None, {})])
    admin = headers_for(client, admin_with(make_user, "review"))
    body = {"reason": "other", "note": "ملاحظة سرية للمراجع"}
    res = client.post(f"/api/admin/requests/{request.id}/reject", json=body, headers=admin)
    assert res.status_code == 200
    res = client.get(LIST, headers=h)
    (item,) = res.json()["items"]
    assert (item["kind"], item["reason_label"]) == ("rejected", "سبب آخر")
    assert "ملاحظة سرية" not in res.text


def test_paging_and_read_all(client, db, marketer, h) -> None:
    for _ in range(5):
        notification_service.add(db, request_factory(db, marketer), "approved")
    db.flush()
    first = client.get(LIST, params={"limit": 2}, headers=h).json()
    assert len(first["items"]) == 2 and first["next_before"] is not None
    rest = client.get(LIST, params={"limit": 50, "before": first["next_before"]}, headers=h).json()
    assert len(rest["items"]) == 3 and rest["next_before"] is None
    assert client.get(LIST, params={"limit": 0}, headers=h).status_code == 422
    assert client.get(LIST, params={"limit": 51}, headers=h).status_code == 422

    assert client.post(f"{LIST}/read-all", headers=h).status_code == 204
    assert _count(client, h) == 0


def test_only_own_notifications(client, db, make_user, marketer, h) -> None:
    other = make_user("marketer")
    theirs = notification_service.add(db, request_factory(db, other), "approved")
    db.flush()
    assert client.get(LIST, headers=h).json()["items"] == []
    assert _count(client, h) == 0
    res = client.post(f"{LIST}/{theirs.id}/read", headers=h)
    assert (res.status_code, res.json()["code"]) == (404, "notification_not_found")
    client.post(f"{LIST}/read-all", headers=h)
    db.expire_all()
    assert db.get(Notification, theirs.id).read_at is None


def test_admins_get_403(client, make_user) -> None:
    admin = headers_for(client, make_user("super_admin"))
    for method, path in (
        ("get", LIST),
        ("get", f"{LIST}/unread-count"),
        ("post", f"{LIST}/read-all"),
        ("post", f"{LIST}/1/read"),
    ):
        assert getattr(client, method)(path, headers=admin).status_code == 403, path


# --- US4: deleted requests (T035) -------------------------------------------------------------


def test_a_deleted_request_shows_no_name(client, db, make_user, marketer, h) -> None:
    admin = admin_with(make_user, "review", "delete")
    request = request_factory(db, marketer, status="rejected", rejection_reason="card_unclear")
    notification_service.add(db, request, "rejected", "card_unclear")
    name = request.full_name
    mark_deleted(db, request, admin, reason="duplicate")
    notification_service.add(db, request, "deleted", "duplicate")
    db.flush()

    res = client.get(LIST, headers=h)
    deleted, rejected = res.json()["items"]
    assert (deleted["kind"], deleted["full_name"], deleted["deleted"]) == ("deleted", None, True)
    assert deleted["reason_label"] == "طلب مكرر"
    assert deleted["number_label"] == request.number_label
    assert (rejected["full_name"], rejected["deleted"]) == (None, True)
    assert rejected["reason_label"] == "صورة البطاقة غير واضحة"
    assert name not in res.text
