"""«طلب العودة للخدمة» (specs/009 US1, US2; FR-003, FR-006 to FR-010, FR-014, FR-015).

Synthetic data only: the fake card reader gives NID / FAMILY; existing subscribers come from the
request factory. The marketer never learns anything about the matched record (FR-012).
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.family_key import family_key
from app.core.timeutil import utc_now
from app.models import AuditLog, Draft, Request, RequestReason
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.submit import (
    PHONE,
    complete_draft,
    get_draft,
    make_catalog,
    marketer_headers,
    patch,
    submit,
    verify,
)

OLD_PHONE = "07709990001"
OLD_USERNAME = "OLD01-07709990001"


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def fake_sender():
    sender = get_otp_sender()
    sender.outbox.clear()
    sender.fail_with = None
    yield sender
    sender.outbox.clear()


@pytest.fixture
def catalog(client, make_user):
    return make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))


@pytest.fixture
def marketer(make_user):
    return make_user("marketer", name="مسوّق تجريبي")


@pytest.fixture
def h(client, marketer):
    return marketer_headers(client, marketer)


def _person(db, make_user, **overrides):
    """The same person as the fake card: national ID and family number on one record."""
    values = {
        "national_id": NID,
        "national_id_input": NID,
        "family_number": FAMILY,
        "phone": OLD_PHONE,
        "username": OLD_USERNAME,
    }
    return request_factory(db, make_user("marketer"), **(values | overrides))


def _audits(db, action):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


# --- the choice on the draft ----------------------------------------------------------------


def test_same_person_offers_return_by_identity(client, db, h, catalog, make_user):
    _person(db, make_user)
    draft = get_draft(client, h, complete_draft(client, h, catalog, verified=False))
    checks = draft["checks"]
    assert checks["national_id_exists"] is True
    assert (checks["return_available"], checks["return_basis"]) == (True, "identity")
    assert (checks["return_chosen"], checks["return_pending"]) == (False, False)
    assert "national_id_exists" in [m["field"] for m in draft["missing"]]


def test_choose_and_withdraw_are_stored_and_audited(client, db, h, catalog, make_user):
    _person(db, make_user)
    draft_id = complete_draft(client, h, catalog, verified=False)

    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["return_chosen"] is True
    assert "national_id_exists" not in [m["field"] for m in chosen["missing"]]
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)).return_key == f"identity:{NID}:{family_key(FAMILY)}"
    (entry,) = _audits(db, "draft.return_chosen")
    assert (entry.entity_type, entry.entity_id, entry.after) == (
        "draft",
        draft_id,
        {"basis": "identity"},
    )

    withdrawn = patch(client, h, draft_id, {"return_chosen": False})
    assert withdrawn["checks"]["return_chosen"] is False
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)).return_key is None
    (entry,) = _audits(db, "draft.return_withdrawn")
    assert entry.entity_id == draft_id


def test_choose_without_a_target_is_refused(client, h, catalog):
    draft_id = complete_draft(client, h, catalog)
    version = get_draft(client, h, draft_id)["version"]
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": version, "changes": {"return_chosen": True}},
        headers=h,
    )
    assert (res.status_code, res.json()["code"]) == (422, "no_return_match")


def test_return_and_second_subscription_exclude_each_other(client, db, h, catalog, make_user):
    _person(db, make_user)
    request_factory(db, make_user("marketer"), family_number=FAMILY)  # a relative
    draft_id = complete_draft(client, h, catalog, verified=False)

    patch(client, h, draft_id, {"additional_confirmed": True})
    after = patch(client, h, draft_id, {"return_chosen": True})
    assert (after["checks"]["return_chosen"], after["checks"]["additional_confirmed"]) == (
        True,
        False,
    )
    back = patch(client, h, draft_id, {"additional_confirmed": True})
    assert (back["checks"]["return_chosen"], back["checks"]["additional_confirmed"]) == (
        False,
        True,
    )


def test_changing_a_number_drops_the_choice(client, db, h, catalog, make_user):
    _person(db, make_user)
    draft_id = complete_draft(client, h, catalog, verified=False)
    patch(client, h, draft_id, {"return_chosen": True})

    out = patch(client, h, draft_id, {"family_number": "9999Z0000000000009"})
    assert out["checks"]["return_chosen"] is False
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)).return_key is None


# --- submission -------------------------------------------------------------------------------


def test_return_by_identity_is_submitted_for_approval(client, db, h, catalog, make_user):
    old = _person(db, make_user)
    draft_id = complete_draft(client, h, catalog, verified=False)
    patch(client, h, draft_id, {"return_chosen": True})
    verify(client, h, draft_id)

    res = submit(client, h, draft_id)

    assert res.status_code == 201, res.json()
    body = res.json()
    assert (body["type"], body["status"], body["result"]) == (
        "return",
        "pending_review",
        "pending_approval",
    )
    assert body["reasons"] == ["return"]
    assert body["username"] is None  # shown after approval only
    request = db.get(Request, body["id"])
    assert request.username == OLD_USERNAME  # FR-015: the historical username
    (reason,) = db.scalars(select(RequestReason).where(RequestReason.request_id == body["id"]))
    assert (reason.reason, reason.matched_source, reason.matched_ref, reason.details) == (
        "return",
        "sijil",
        str(old.id),
        {"basis": "identity"},
    )
    (entry,) = _audits(db, "request.submitted")
    assert entry.after["reasons"] == ["return"] and entry.after["type"] == "return"


def test_return_with_a_pending_record_is_refused(client, db, h, catalog, make_user):
    _person(db, make_user, status="pending_review")
    draft_id = complete_draft(client, h, catalog, verified=False)
    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["return_pending"] is True
    assert "return_pending" in [m["field"] for m in chosen["missing"]]
    verify(client, h, draft_id)

    res = submit(client, h, draft_id)

    assert (res.status_code, res.json()["code"]) == (409, "return_pending")
    assert res.json()["message"] == "يوجد طلب سابق بالانتظار لهذا المشترك"
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    (entry,) = _audits(db, "request.submit_refused")
    assert entry.after == {"reason": "return_pending"}


def test_choice_gone_stale_at_submission_falls_back(client, db, h, catalog, make_user):
    old = _person(db, make_user)
    draft_id = complete_draft(client, h, catalog, verified=False)
    patch(client, h, draft_id, {"return_chosen": True})
    verify(client, h, draft_id)
    # The record stops counting before the submission (with the 010 decision columns).
    old.status = "rejected"
    old.approved_at = None
    old.rejected_at = utc_now()
    old.rejected_by = old.marketer_id
    old.rejection_reason = "card_unclear"
    db.flush()

    res = submit(client, h, draft_id)

    assert res.status_code == 201, res.json()
    assert (res.json()["type"], res.json()["result"]) == ("new", "approved")


def test_return_draft_still_needs_the_card_images(client, db, h, make_user):
    _person(db, make_user)
    draft_id = str(uuid.uuid4())
    res = client.put(
        f"/api/drafts/{draft_id}",
        json={"changes": {"national_id": NID, "family_number": FAMILY}},
        headers=h,
    )
    assert res.status_code == 201, res.json()
    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["return_chosen"] is True

    res = submit(client, h, draft_id)

    assert (res.status_code, res.json()["code"]) == (422, "draft_incomplete")
    fields = [m["field"] for m in res.json()["missing"]]
    assert {"image_front", "image_back"} <= set(fields)


def test_marketer_responses_name_no_one(client, db, h, catalog, make_user):
    old = _person(db, make_user, full_name="اسم مطابق سري")
    draft_id = complete_draft(client, h, catalog, verified=False)
    texts = [patch(client, h, draft_id, {"return_chosen": True})]
    verify(client, h, draft_id)
    texts.append(submit(client, h, draft_id).json())
    blob = str(texts)
    for secret in (old.full_name, OLD_PHONE, OLD_USERNAME, old.tower_code, f"T3C-{old.number}"):
        assert secret not in blob
    assert PHONE in blob  # the new subscription's own phone is fine


# --- phone basis (US2, T025) --------------------------------------------------------------------


def _phone_owner(db, make_user, **overrides):
    """A subscriber with PHONE whose numbers differ from the fake card's."""
    return request_factory(db, make_user("marketer"), phone=PHONE, **overrides)


def test_used_phone_offers_return_by_phone(client, db, h, catalog, make_user):
    _phone_owner(db, make_user)
    draft = get_draft(client, h, complete_draft(client, h, catalog, verified=False))
    checks = draft["checks"]
    assert (checks["phone_used"], checks["return_available"], checks["return_basis"]) == (
        True,
        True,
        "phone",
    )
    assert checks["national_id_exists"] is False


def test_return_by_phone_sends_the_code_and_submits(client, db, h, catalog, make_user):
    old = _phone_owner(db, make_user)
    draft_id = complete_draft(client, h, catalog, verified=False)
    res = client.post(f"/api/drafts/{draft_id}/otp/send", headers=h)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")

    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["phone_used"] is False
    assert "phone_used" not in [m["field"] for m in chosen["missing"]]
    (entry,) = _audits(db, "draft.return_chosen")
    assert entry.after == {"basis": "phone"}
    verify(client, h, draft_id)

    res = submit(client, h, draft_id)

    assert res.status_code == 201, res.json()
    assert (res.json()["type"], res.json()["result"]) == ("return", "pending_approval")
    (reason,) = db.scalars(
        select(RequestReason).where(RequestReason.request_id == res.json()["id"])
    )
    assert (reason.reason, reason.matched_ref, reason.details) == (
        "return",
        str(old.id),
        {"basis": "phone"},
    )


def test_phone_of_a_and_card_of_b_returns_b_only(client, db, h, catalog, make_user):
    _phone_owner(db, make_user)  # A
    _person(db, make_user)  # B: the card's person, with another phone
    draft_id = complete_draft(client, h, catalog, verified=False)
    assert get_draft(client, h, draft_id)["checks"]["return_basis"] == "identity"

    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["return_chosen"] is True
    assert chosen["checks"]["phone_used"] is True  # A's phone is still refused
    res = client.post(f"/api/drafts/{draft_id}/otp/send", headers=h)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")


def test_phone_and_identity_on_the_same_record_offer_one_return(client, db, h, catalog, make_user):
    _person(db, make_user, phone=PHONE)
    draft_id = complete_draft(client, h, catalog, verified=False)
    checks = get_draft(client, h, draft_id)["checks"]
    assert checks["return_basis"] == "identity"
    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["phone_used"] is False  # the person's own phone
    verify(client, h, draft_id)
    res = submit(client, h, draft_id)
    assert res.status_code == 201, res.json()
    assert (
        len(
            list(
                db.scalars(
                    select(RequestReason).where(RequestReason.request_id == res.json()["id"])
                )
            )
        )
        == 1
    )
