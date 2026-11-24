"""«تم الربط» (specs/013 US1: FR-005 to FR-007, FR-020; research R2, R3). Synthetic data only."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, Notification, RequestLink
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def linker(make_user):
    return admin_with(make_user, "link", name="أدمن الربط")


@pytest.fixture
def h(client, linker):
    return headers_for(client, linker)


def _link(client, h, request_id):
    return client.post(f"/api/admin/requests/{request_id}/link", headers=h)


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def _writes(db, request) -> tuple[int, int, int]:
    """(link history rows, link audits, link notifications) for `request`."""
    return (
        _count(db, RequestLink, RequestLink.request_id == request.id),
        _count(
            db,
            AuditLog,
            AuditLog.action == "request.linked",
            AuditLog.entity_id == str(request.number),
        ),
        _count(
            db,
            Notification,
            Notification.request_id == request.id,
            Notification.kind == "linked",
        ),
    )


def test_link_an_accepted_request(client, db, h, linker, marketer, frozen_clock) -> None:
    accepted_at = NOW - timedelta(days=2)
    request = request_factory(
        db, marketer, status="approved", approved_at=accepted_at, approved_by=linker.id
    )
    frozen_clock.set(NOW)

    res = _link(client, h, request.id)

    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["id"] == request.id
    assert body["number_label"] == request.number_label
    assert body["linked_at"] is not None
    assert body["linked_by_name"] == "أدمن الربط"
    db.refresh(request)
    assert (request.status, request.linked_at, request.linked_by) == ("linked", NOW, linker.id)
    # The acceptance is its own fact (constitution Principle IV).
    assert (request.approved_at, request.approved_by, request.counts_commission) == (
        accepted_at,
        linker.id,
        True,
    )

    history = db.scalars(select(RequestLink).where(RequestLink.request_id == request.id)).all()
    assert [(r.kind, r.actor_id, r.at, r.reason) for r in history] == [
        ("linked", linker.id, NOW, None)
    ]
    assert body["link_id"] == history[0].id

    (audit,) = db.scalars(select(AuditLog).where(AuditLog.action == "request.linked")).all()
    assert (audit.actor_id, audit.entity_type, audit.entity_id) == (
        linker.id,
        "request",
        str(request.number),
    )
    assert (audit.before, audit.after) == ({"status": "approved"}, {"status": "linked"})

    (note,) = db.scalars(select(Notification).where(Notification.request_id == request.id)).all()
    assert (note.marketer_id, note.kind, note.reason) == (marketer.id, "linked", None)


def test_the_main_admin_may_link(client, db, make_user, marketer) -> None:
    request = request_factory(db, marketer, status="approved")
    res = _link(client, headers_for(client, make_user("super_admin")), request.id)
    assert res.status_code == 200, res.json()


@pytest.mark.parametrize(
    ("status", "code"),
    [("pending_review", "invalid_transition"), ("rejected", "invalid_transition")],
)
def test_not_accepted_is_refused(client, db, h, marketer, status, code) -> None:
    request = request_factory(db, marketer, status=status)
    res = _link(client, h, request.id)
    assert (res.status_code, res.json()["code"]) == (409, code)
    db.refresh(request)
    assert (request.status, request.linked_at) == (status, None)
    assert _writes(db, request) == (0, 0, 0)


@pytest.mark.parametrize("status", ["pending_review", "rejected"])
def test_deleted_is_refused(client, db, h, linker, marketer, status) -> None:
    request = mark_deleted(db, request_factory(db, marketer, status=status), linker)
    res = _link(client, h, request.id)
    assert (res.status_code, res.json()["code"]) == (409, "request_deleted")
    assert _writes(db, request) == (0, 0, 0)


def test_already_linked_is_refused(client, db, h, marketer) -> None:
    request = request_factory(db, marketer, status="linked")
    linked_at, linked_by = request.linked_at, request.linked_by

    res = _link(client, h, request.id)

    assert (res.status_code, res.json()["code"]) == (409, "already_linked")
    assert res.json()["message"] == "تم ربط هذا الطلب مسبقاً"
    db.refresh(request)
    assert (request.linked_at, request.linked_by) == (linked_at, linked_by)
    # Only the factory's own history row; no audit, no notification.
    assert _writes(db, request) == (1, 0, 0)


def test_twice_by_the_same_admin_links_once(client, db, h, marketer) -> None:
    request = request_factory(db, marketer, status="approved")
    assert _link(client, h, request.id).status_code == 200
    assert _link(client, h, request.id).json()["code"] == "already_linked"
    assert _writes(db, request) == (1, 1, 1)


def test_unknown_request_is_404(client, h) -> None:
    res = _link(client, h, 987654321)
    assert (res.status_code, res.json()["code"]) == (404, "request_not_found")


@pytest.mark.parametrize("who", ["review_admin", "marketer"])
def test_without_link_permission_is_403(client, db, make_user, marketer, who) -> None:
    request = request_factory(db, marketer, status="approved")
    caller = admin_with(make_user, "review", "delete") if who == "review_admin" else marketer
    res = _link(client, headers_for(client, caller), request.id)
    assert res.status_code == 403
    db.refresh(request)
    assert request.status == "approved"
    assert _writes(db, request) == (0, 0, 0)


def test_link_and_undo_logs_hold_no_personal_data(client, db, h, marketer, caplog) -> None:
    """specs/013 T048 (constitution Principle II): the action, the number and the reason code
    only."""
    import logging

    caplog.set_level(logging.INFO)
    request = request_factory(db, marketer, status="approved", phone="07801239876")
    linked = _link(client, h, request.id)
    client.post(
        f"/api/admin/requests/{request.id}/unlink",
        json={"reason": "by_mistake", "link_id": linked.json()["link_id"]},
        headers=h,
    )

    lines = [r.getMessage() for r in caplog.records if r.name == "sijil.links"]
    assert lines == [
        f"link number={request.number}",
        f"unlink number={request.number} reason=by_mistake",
    ]
    for secret in (
        request.full_name,
        request.phone,
        request.username,
        request.national_id,
        request.family_number,
    ):
        assert secret not in caplog.text
