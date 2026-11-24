"""«التراجع عن الربط» (specs/013 US3: FR-008 to FR-010, FR-016, FR-020, FR-022; research R2–R4).

Synthetic data only.
"""

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


def _current_link(db, request) -> int:
    return db.scalar(
        select(RequestLink.id)
        .where(RequestLink.request_id == request.id, RequestLink.kind == "linked")
        .order_by(RequestLink.id.desc())
    )


def _unlink(client, h, request_id, body):
    return client.post(f"/api/admin/requests/{request_id}/unlink", json=body, headers=h)


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def _writes(db, request) -> tuple[int, int, int]:
    """(undo history rows, undo audits, undo notifications) for `request`."""
    return (
        _count(
            db, RequestLink, RequestLink.request_id == request.id, RequestLink.kind == "unlinked"
        ),
        _count(
            db,
            AuditLog,
            AuditLog.action == "request.unlinked",
            AuditLog.entity_id == str(request.number),
        ),
        _count(
            db, Notification, Notification.request_id == request.id, Notification.kind == "unlinked"
        ),
    )


def test_undo_a_link(client, db, h, linker, make_user, marketer, frozen_clock) -> None:
    accepted_at = NOW - timedelta(days=3)
    request = request_factory(
        db,
        marketer,
        status="linked",
        type="return",
        counts_commission=False,
        approved_at=accepted_at,
        approved_by=linker.id,
        linked_at=NOW - timedelta(days=1),
    )
    frozen_clock.set(NOW)

    res = _unlink(
        client, h, request.id, {"reason": "by_mistake", "link_id": _current_link(db, request)}
    )

    assert res.status_code == 200, res.json()
    body = res.json()
    assert (body["id"], body["linked_at"], body["link_id"]) == (request.id, None, None)
    db.refresh(request)
    assert (request.status, request.linked_at, request.linked_by) == ("approved", None, None)
    # The acceptance and the commission answer stay (FR-010).
    assert (request.approved_at, request.approved_by, request.counts_commission) == (
        accepted_at,
        linker.id,
        False,
    )

    history = db.scalars(
        select(RequestLink).where(RequestLink.request_id == request.id).order_by(RequestLink.id)
    ).all()
    assert [(r.kind, r.reason) for r in history] == [("linked", None), ("unlinked", "by_mistake")]
    assert (history[1].actor_id, history[1].at) == (linker.id, NOW)

    (audit,) = db.scalars(select(AuditLog).where(AuditLog.action == "request.unlinked")).all()
    assert (audit.actor_id, audit.entity_type, audit.entity_id) == (
        linker.id,
        "request",
        str(request.number),
    )
    assert (audit.before, audit.after) == (
        {"status": "linked"},
        {"status": "approved", "reason": "by_mistake"},
    )

    (note,) = db.scalars(select(Notification).where(Notification.request_id == request.id)).all()
    assert (note.marketer_id, note.kind, note.reason) == (marketer.id, "unlinked", "by_mistake")
    listed = client.get("/api/notifications", headers=headers_for(client, marketer)).json()
    assert listed["items"][0]["reason_label"] == "ضُغط بالخطأ"


@pytest.mark.parametrize(
    "reason", ["not_linked_in_sas", "by_mistake", "other_request_linked", "other"]
)
def test_each_reason_is_accepted(client, db, h, marketer, reason) -> None:
    request = request_factory(db, marketer, status="linked")
    res = _unlink(client, h, request.id, {"reason": reason, "link_id": _current_link(db, request)})
    assert res.status_code == 200, res.json()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reason": "by_mistake"},
        {"link_id": 1},
        {"reason": "guess", "link_id": 1},
        {"reason": "", "link_id": 1},
        {"reason": "other", "link_id": 1, "note": "نص حر"},
        {"reason": "other", "link_id": "1"},
    ],
)
def test_bad_body_is_422(client, db, h, marketer, body) -> None:
    request = request_factory(db, marketer, status="linked")
    if "link_id" in body and body["link_id"] == 1:
        body = {**body, "link_id": _current_link(db, request)}
    res = _unlink(client, h, request.id, body)
    assert res.status_code == 422
    db.refresh(request)
    assert request.status == "linked"
    assert _writes(db, request) == (0, 0, 0)


def test_a_stale_link_id_is_already_unlinked(client, db, h, linker, marketer) -> None:
    """The page showed an older link; another admin undid and linked it again since."""
    request = request_factory(db, marketer, status="linked")
    stale = _current_link(db, request)
    assert (
        _unlink(client, h, request.id, {"reason": "by_mistake", "link_id": stale}).status_code
        == 200
    )
    assert client.post(f"/api/admin/requests/{request.id}/link", headers=h).status_code == 200

    res = _unlink(client, h, request.id, {"reason": "by_mistake", "link_id": stale})

    assert (res.status_code, res.json()["code"]) == (409, "already_unlinked")
    assert res.json()["message"] == "تم التراجع عن هذا الربط مسبقاً"
    db.refresh(request)
    assert request.status == "linked"
    assert _writes(db, request) == (1, 1, 1)


def test_a_second_undo_is_already_unlinked(client, db, h, marketer) -> None:
    request = request_factory(db, marketer, status="linked")
    body = {"reason": "by_mistake", "link_id": _current_link(db, request)}
    assert _unlink(client, h, request.id, body).status_code == 200

    res = _unlink(client, h, request.id, body)

    assert (res.status_code, res.json()["code"]) == (409, "already_unlinked")
    assert _writes(db, request) == (1, 1, 1)


@pytest.mark.parametrize("status", ["pending_review", "rejected"])
def test_not_linked_is_refused(client, db, h, marketer, status) -> None:
    request = request_factory(db, marketer, status=status)
    res = _unlink(client, h, request.id, {"reason": "by_mistake", "link_id": 1})
    assert (res.status_code, res.json()["code"]) == (409, "invalid_transition")
    assert _writes(db, request) == (0, 0, 0)


@pytest.mark.parametrize("status", ["pending_review", "rejected"])
def test_deleted_is_refused(client, db, h, linker, marketer, status) -> None:
    request = mark_deleted(db, request_factory(db, marketer, status=status), linker)
    res = _unlink(client, h, request.id, {"reason": "by_mistake", "link_id": 1})
    assert (res.status_code, res.json()["code"]) == (409, "request_deleted")
    assert _writes(db, request) == (0, 0, 0)


def test_unknown_request_is_404(client, h) -> None:
    res = _unlink(client, h, 987654321, {"reason": "by_mistake", "link_id": 1})
    assert (res.status_code, res.json()["code"]) == (404, "request_not_found")


@pytest.mark.parametrize("who", ["review_admin", "marketer"])
def test_without_link_permission_is_403(client, db, make_user, marketer, who) -> None:
    request = request_factory(db, marketer, status="linked")
    caller = admin_with(make_user, "review", "delete") if who == "review_admin" else marketer
    res = _unlink(
        client,
        headers_for(client, caller),
        request.id,
        {"reason": "by_mistake", "link_id": _current_link(db, request)},
    )
    assert res.status_code == 403
    db.refresh(request)
    assert request.status == "linked"
    assert _writes(db, request) == (0, 0, 0)
