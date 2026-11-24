"""«قبول» and «رفض» (specs/010 US2: FR-006 to FR-010, FR-017, FR-018; research R1, R2, R6, R7).
Synthetic data only."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import AuditLog, Request
from app.services import match_service
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for, pending_request

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def reviewer(make_user):
    return admin_with(make_user, "review", name="أدمن المراجعة")


@pytest.fixture
def h(client, reviewer):
    return headers_for(client, reviewer)


def _accept(client, h, request_id, body=None):
    return client.post(f"/api/admin/requests/{request_id}/accept", json=body or {}, headers=h)


def _reject(client, h, request_id, body):
    return client.post(f"/api/admin/requests/{request_id}/reject", json=body, headers=h)


def _audits(db, action):
    return db.scalars(select(AuditLog).where(AuditLog.action == action)).all()


def _family(db, marketer):
    old = request_factory(db, marketer)
    return pending_request(db, marketer, [("family_exists", old, {})], type="additional")


def _return(db, marketer):
    """The same person (national ID and family number of `old`): no warning."""
    old = request_factory(db, marketer)
    return pending_request(
        db,
        marketer,
        [("return", old, {"basis": "identity"})],
        type="return",
        username="OLD-1",
        national_id=old.national_id,
        national_id_input=old.national_id,
        family_number=old.family_number,
    )


# --- accept ---


def test_accept_a_family_request(client, db, h, reviewer, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    request = _family(db, marketer)
    username = request.username

    res = _accept(client, h, request.id)

    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["status"] == "approved"
    assert body["decision"]["by"] == "أدمن المراجعة"
    db.refresh(request)
    assert (request.status, request.approved_by) == ("approved", reviewer.id)
    assert request.approved_at == NOW
    assert request.counts_commission is True
    assert request.approval_warnings is None
    assert request.username == username  # FR-010
    (entry,) = _audits(db, "request.approved")
    assert (entry.actor_id, entry.entity_id) == (reviewer.id, str(request.number))
    assert entry.before == {"status": "pending_review"}
    assert entry.after == {
        "status": "approved",
        "type": "additional",
        "counts_commission": True,
        "despite_warnings": [],
    }


def test_return_needs_the_commission_answer(client, db, h, marketer) -> None:
    request = _return(db, marketer)

    res = _accept(client, h, request.id)
    assert res.status_code == 422
    assert res.json()["code"] == "commission_answer_required"
    db.refresh(request)
    assert request.status == "pending_review"

    res = _accept(client, h, request.id, {"counts_commission": False})
    assert res.status_code == 200, res.json()
    db.refresh(request)
    assert (request.status, request.counts_commission) == ("approved", False)
    assert request.username == "OLD-1"  # the historical username stays
    assert _audits(db, "request.approved")[0].after["counts_commission"] is False


def test_commission_answer_is_refused_for_other_types(client, db, h, marketer) -> None:
    request = _family(db, marketer)
    res = _accept(client, h, request.id, {"counts_commission": False})
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


# --- reject ---


def test_reject_with_a_fixed_reason(client, db, h, reviewer, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    request = _family(db, marketer)

    res = _reject(client, h, request.id, {"reason": "card_unclear"})

    assert res.status_code == 200, res.json()
    assert res.json()["decision"]["label"] == "صورة البطاقة غير واضحة"
    db.refresh(request)
    assert (request.status, request.rejected_by, request.rejected_at) == (
        "rejected",
        reviewer.id,
        NOW,
    )
    assert (request.rejection_reason, request.rejection_note) == ("card_unclear", None)
    assert request.approved_at is None
    (entry,) = _audits(db, "request.rejected")
    assert entry.before == {"status": "pending_review"}
    assert entry.after == {"status": "rejected", "reason": "card_unclear", "note": None}


def test_other_needs_a_note_and_stores_it_trimmed(client, db, h, marketer) -> None:
    request = _family(db, marketer)

    res = _reject(client, h, request.id, {"reason": "other", "note": "   "})
    assert res.status_code == 422
    assert res.json()["code"] == "rejection_note_required"

    res = _reject(client, h, request.id, {"reason": "other", "note": "  طلب مكرر  "})
    assert res.status_code == 200, res.json()
    db.refresh(request)
    assert (request.rejection_reason, request.rejection_note) == ("other", "طلب مكرر")


def test_note_with_a_fixed_reason_is_refused(client, db, h, marketer) -> None:
    request = _family(db, marketer)
    res = _reject(client, h, request.id, {"reason": "card_unclear", "note": "نص إضافي"})
    assert res.status_code == 422
    db.refresh(request)
    assert request.status == "pending_review"


# --- one decision, permissions, and FR-018 ---


@pytest.mark.parametrize("first", ["accept", "reject"])
def test_second_decision_is_already_decided(client, db, h, marketer, first) -> None:
    request = _family(db, marketer)
    if first == "accept":
        assert _accept(client, h, request.id).status_code == 200
    else:
        assert _reject(client, h, request.id, {"reason": "card_unclear"}).status_code == 200
    expected = "approved" if first == "accept" else "rejected"

    for res in (
        _accept(client, h, request.id),
        _reject(client, h, request.id, {"reason": "card_unclear"}),
    ):
        assert res.status_code == 409
        assert res.json()["code"] == "already_decided"
        assert res.json()["status"] == expected


@pytest.mark.parametrize("who", ["settings_admin", "marketer"])
def test_others_get_404(client, db, make_user, marketer, who) -> None:
    request = _family(db, marketer)
    user = admin_with(make_user, "settings") if who == "settings_admin" else marketer
    headers = headers_for(client, user)
    assert _accept(client, headers, request.id).status_code == 404
    assert _reject(client, headers, request.id, {"reason": "card_unclear"}).status_code == 404
    db.refresh(request)
    assert request.status == "pending_review"


def test_main_admin_can_decide(client, db, make_user, marketer) -> None:
    request = _family(db, marketer)
    res = _accept(client, headers_for(client, make_user("super_admin")), request.id)
    assert res.status_code == 200


def test_rejected_request_no_longer_counts(client, db, h, marketer) -> None:
    """FR-018: after «رفض» the same phone and numbers are free for a new request."""
    request = _family(db, marketer)
    keys = {
        "phone": request.phone,
        "national_id": request.national_id,
        "family_key": request.family_key,
    }
    own = str(request.id)
    assert any(r.ref_id == own for r in match_service.find_matches(db, **keys).records)

    assert _reject(client, h, request.id, {"reason": "card_unclear"}).status_code == 200

    assert all(r.ref_id != own for r in match_service.find_matches(db, **keys).records)
    assert db.get(Request, request.id).status == "rejected"


# --- specs/011 T019: a deleted request takes no decision ----------------------------------------


@pytest.mark.parametrize(
    "action,body",
    [("accept", {}), ("reject", {"reason": "card_unclear"})],
)
def test_deleted_request_cannot_be_decided(client, db, h, reviewer, marketer, action, body) -> None:
    from tests.helpers.requests import mark_deleted

    request = mark_deleted(db, request_factory(db, marketer, status="pending_review"), reviewer)
    res = client.post(f"/api/admin/requests/{request.id}/{action}", json=body, headers=h)
    assert (res.status_code, res.json()["code"]) == (409, "request_deleted")
    db.expire_all()
    row = db.get(Request, request.id)
    assert row.status == "pending_review" and row.approved_at is None and row.rejected_at is None


# --- specs/012 T023: each decision notifies the marketer once ------------------------------------


def _notifications(db, request):
    from app.models import Notification

    db.expire_all()
    return db.scalars(select(Notification).where(Notification.request_id == request.id)).all()


def test_accept_adds_one_approved_notification(client, db, h, marketer) -> None:
    request = _family(db, marketer)
    assert _accept(client, h, request.id).status_code == 200
    (row,) = _notifications(db, request)
    assert (row.marketer_id, row.kind, row.reason, row.read_at) == (
        marketer.id,
        "approved",
        None,
        None,
    )


@pytest.mark.parametrize(
    "body,reason",
    [
        ({"reason": "card_unclear"}, "card_unclear"),
        ({"reason": "other", "note": "ملاحظة المراجع التجريبية"}, "other"),
    ],
)
def test_reject_adds_one_rejected_notification_with_the_code(
    client, db, h, marketer, body, reason
) -> None:
    request = _family(db, marketer)
    assert _reject(client, h, request.id, body).status_code == 200
    (row,) = _notifications(db, request)
    assert (row.marketer_id, row.kind, row.reason) == (marketer.id, "rejected", reason)


def test_refused_decisions_add_no_notification(client, db, h, marketer) -> None:
    # 409 already decided: only the first decision notifies.
    request = _family(db, marketer)
    assert _accept(client, h, request.id).status_code == 200
    assert _accept(client, h, request.id).status_code == 409
    assert _reject(client, h, request.id, {"reason": "card_unclear"}).status_code == 409
    assert [r.kind for r in _notifications(db, request)] == ["approved"]

    # 422: a return without the commission answer, an «سبب آخر» without its note.
    ret = _return(db, marketer)
    assert _accept(client, h, ret.id).status_code == 422
    other = _family(db, marketer)
    assert _reject(client, h, other.id, {"reason": "other"}).status_code == 422
    assert _notifications(db, ret) == [] and _notifications(db, other) == []
