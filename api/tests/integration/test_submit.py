"""Submission (specs/008 US1–US2: tasks T017–T019, T030; FR-011 to FR-021).

Synthetic data only: the fake card reader, made-up phones, factory requests.
"""

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.config import get_settings
from app.models import (
    AuditLog,
    CardReading,
    Draft,
    DraftImage,
    Plan,
    Request,
    RequestImage,
    RequestReason,
)
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.submit import (
    PHONE,
    SETTINGS,
    complete_draft,
    get_draft,
    make_catalog,
    marketer_headers,
    patch,
    submit,
    verify,
)


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
def admin(client, make_user):
    return auth_header(login(client, make_user("super_admin").phone))


@pytest.fixture
def catalog(client, admin):
    return make_catalog(client, admin)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer", name="مسوّق تجريبي")


@pytest.fixture
def h(client, marketer):
    return marketer_headers(client, marketer)


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- US1: the clean path ---------------------------------------------------------------------


def test_clean_draft_is_approved_with_number_and_username(client, db, h, catalog, uploads):
    draft_id = complete_draft(client, h, catalog)
    draft = db.get(Draft, uuid.UUID(draft_id))
    verified_at = draft.otp_verified_at
    files = {img.side: (img.id, img.file_name) for img in draft.images}

    res = submit(client, h, draft_id)

    assert res.status_code == 201, res.json()
    body = res.json()
    # The sequence starts at 1001 (test_migration_0010); it does not roll back between tests.
    assert body["number"] >= 1001 and body["number_label"] == f"T3C-{body['number']}"
    assert (body["type"], body["status"], body["result"]) == ("new", "approved", "approved")
    assert body["reasons"] == []
    assert body["username"] == f"ALM03-{PHONE}"
    assert body["approved_at"] == body["submitted_at"]
    assert (body["tower_code"], body["area_name"], body["plan_name"]) == ("ALM03", "العلم", "PLUS")
    assert (body["trial_price"], body["second_price"]) == (20000, 35000)
    for secret in (NID, FAMILY, "card_readings"):
        assert secret not in res.text

    req = db.get(Request, body["id"])
    assert req.draft_id == uuid.UUID(draft_id)
    assert req.approved_by is None and req.approved_at == req.submitted_at
    assert req.otp_verified_at == verified_at
    assert (req.national_id, req.family_number, req.phone) == (NID, FAMILY, PHONE)
    assert req.card_fields["national_id"]["source"] == "card"
    assert set(req.card_readings) == {"front", "back"}
    assert req.card_readings["front"]["raw"] is not None
    assert req.great_grandfather_name == "مثال" and req.location_source == "gps"

    # The draft is gone; its images live on as request images with the same files.
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is None
    assert _count(db, DraftImage) == 0 and _count(db, CardReading) == 0
    images = {img.side: (img.id, img.file_name) for img in db.get(Request, body["id"]).images}
    assert images == files
    for _, name in images.values():
        assert (uploads / name).exists()


def test_submitted_draft_leaves_the_drafts_list(client, h, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    assert submit(client, h, draft_id).status_code == 201
    assert client.get("/api/drafts", headers=h).json()["items"] == []
    assert client.get(f"/api/drafts/{draft_id}", headers=h).status_code == 404
    v = {"version": 1, "changes": {"address": "x"}}
    assert client.patch(f"/api/drafts/{draft_id}", json=v, headers=h).status_code == 404
    assert client.delete(f"/api/drafts/{draft_id}", headers=h).status_code == 404


def test_values_are_fixed_after_a_price_change(client, db, h, admin, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    number = submit(client, h, draft_id).json()["id"]
    res = client.patch(
        f"{SETTINGS}/plans/{catalog['plus']['id']}",
        json={"trial_price": 25000, "second_price": 40000},
        headers=admin,
    )
    assert res.status_code == 200, res.json()
    db.expire_all()
    req = db.get(Request, number)
    assert (req.trial_price, req.second_price, req.plan_name) == (20000, 35000, "PLUS")


def test_numbers_go_up_and_are_audited(client, db, h, catalog) -> None:
    first = submit(client, h, complete_draft(client, h, catalog)).json()
    # A second, different subscriber typed by hand (so it waits for review, still numbered).
    second_id = complete_draft(
        client,
        h,
        catalog,
        phone="07801234568",
        read_card=False,
    )
    second = submit(client, h, second_id).json()
    assert second["number"] == first["number"] + 1
    entries = db.scalars(
        select(AuditLog).where(AuditLog.action == "request.submitted").order_by(AuditLog.id)
    ).all()
    assert [e.entity_id for e in entries] == [str(first["number"]), str(second["number"])]
    assert entries[0].entity_type == "request"
    assert entries[0].after == {
        "number": first["number"],
        "type": "new",
        "status": "approved",
        "reasons": [],
        "tower_code": "ALM03",
        "plan_name": "PLUS",
    }


# --- US1: refusals keep the draft ------------------------------------------------------------


def _unchanged(db, draft_id: str) -> None:
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    assert _count(db, Request) == 0


def test_missing_item_refuses(client, db, h, catalog) -> None:
    draft_id = complete_draft(client, h, catalog, verified=False)
    patch(client, h, draft_id, {"landmark": None})
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (422, "draft_incomplete")
    assert {"field": "landmark", "code": "required"} in res.json()["missing"]
    _unchanged(db, draft_id)


def test_expired_card_refuses(client, db, h, catalog) -> None:
    """The card was valid when filled and expired before sending (checked again at submit)."""
    draft_id = complete_draft(client, h, catalog)
    draft = db.get(Draft, uuid.UUID(draft_id))
    draft.expiry_date = date(2020, 1, 1)  # stands for "the expiry date has passed"
    db.flush()
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (422, "draft_incomplete")
    assert {"field": "card_expired", "code": "card_expired"} in res.json()["missing"]
    _unchanged(db, draft_id)


def test_unconfirmed_national_id_refuses(client, db, h, catalog) -> None:
    draft_id = complete_draft(client, h, catalog, verified=False)
    # The back's MRZ carries NID; a different front number is a mismatch until confirmed.
    patch(client, h, draft_id, {"national_id": "199912345670"})
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (422, "draft_incomplete")
    assert any(m["field"] == "national_id_unconfirmed" for m in res.json()["missing"])
    _unchanged(db, draft_id)


def test_unverified_phone_refuses(client, db, h, catalog) -> None:
    draft_id = complete_draft(client, h, catalog, verified=False)
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "otp_needs_reverify")
    _unchanged(db, draft_id)


def test_context_change_after_verification_refuses(client, db, h, admin, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    # A price change in the settings reaches the draft at submission and cancels the check.
    client.patch(
        f"{SETTINGS}/plans/{catalog['plus']['id']}",
        json={"trial_price": 21000, "second_price": 35000},
        headers=admin,
    )
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "otp_needs_reverify")
    _unchanged(db, draft_id)
    assert get_draft(client, h, draft_id)["trial_price"] == 21000


def test_stale_version_refuses(client, db, h, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    version = get_draft(client, h, draft_id)["version"]
    res = submit(client, h, draft_id, version=version - 1)
    assert (res.status_code, res.json()["code"]) == (409, "draft_conflict")
    _unchanged(db, draft_id)


def test_deactivated_plan_refuses_and_clears_the_choice(client, db, h, admin, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    res = client.post(f"{SETTINGS}/plans/{catalog['plus']['id']}/deactivate", headers=admin)
    assert res.status_code == 200, res.json()
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "catalog_changed")
    assert res.json()["notices"] == [
        {"field": "plan_id", "code": "choice_unavailable", "old": None, "new": None}
    ]
    _unchanged(db, draft_id)
    after = get_draft(client, h, draft_id)
    assert after["plan_id"] is None and after["otp"]["status"] != "verified"


def test_other_marketer_gets_404(client, db, h, catalog, make_user) -> None:
    draft_id = complete_draft(client, h, catalog)
    other = marketer_headers(client, make_user("marketer"))
    res = submit(client, other, draft_id, version=get_draft(client, h, draft_id)["version"])
    assert (res.status_code, res.json()["code"]) == (404, "draft_not_found")
    _unchanged(db, draft_id)


def test_admin_gets_403(client, db, h, admin, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    headers = admin | {"X-Client-Id": str(uuid.uuid4())}
    res = submit(client, headers, draft_id, version=get_draft(client, h, draft_id)["version"])
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")
    _unchanged(db, draft_id)


def test_stopped_marketer_gets_403(client, db, h, marketer, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    version = get_draft(client, h, draft_id)["version"]
    marketer.is_active = False
    db.flush()
    res = submit(client, h, draft_id, version=version)
    assert (res.status_code, res.json()["code"]) == (403, "account_inactive")
    _unchanged(db, draft_id)


# --- US1: idempotent ---------------------------------------------------------------------------


def test_repeat_returns_the_same_request(client, db, h, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    version = get_draft(client, h, draft_id)["version"]
    first = submit(client, h, draft_id, version=version)
    again = submit(client, h, draft_id, version=version)
    number = first.json()["number"]
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    assert _count(db, Request) == 1
    # No number was consumed by the repeat.
    nxt = submit(
        client, h, complete_draft(client, h, catalog, phone="07801234569", read_card=False)
    )
    assert nxt.json()["number"] == number + 1


def test_repeat_by_another_marketer_is_404(client, h, catalog, make_user) -> None:
    draft_id = complete_draft(client, h, catalog)
    version = get_draft(client, h, draft_id)["version"]
    assert submit(client, h, draft_id, version=version).status_code == 201
    other = marketer_headers(client, make_user("marketer"))
    res = submit(client, other, draft_id, version=version)
    assert (res.status_code, res.json()["code"]) == (404, "draft_not_found")


# --- US2: a used phone at submission (T030) ----------------------------------------------------


def test_phone_taken_after_verification_refuses_and_is_audited(
    client, db, h, marketer, catalog
) -> None:
    draft_id = complete_draft(client, h, catalog)
    request_factory(db, marketer, phone=PHONE)
    db.commit()  # another marketer's submission, already committed
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")
    assert res.json()["message"] == "المشترك موجود سابقاً، هل يود العودة للخدمة؟"
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    assert _count(db, Request) == 1  # only the factory request
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "request.submit_refused")).one()
    assert (entry.entity_type, entry.entity_id) == ("draft", draft_id)
    assert entry.after == {"reason": "phone_used"}
    assert entry.actor_id == marketer.id


def test_phone_used_wins_over_a_family_match(client, db, h, marketer, catalog) -> None:
    draft_id = complete_draft(client, h, catalog)
    request_factory(db, marketer, phone=PHONE, family_number=FAMILY)
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")


def test_rejected_request_with_the_phone_does_not_block(client, db, h, marketer, catalog) -> None:
    request_factory(db, marketer, phone=PHONE, status="rejected")
    draft_id = complete_draft(client, h, catalog)
    assert submit(client, h, draft_id).json()["result"] == "approved"


def test_plan_row_is_untouched_by_submission(client, db, h, catalog) -> None:
    submit(client, h, complete_draft(client, h, catalog))
    plan = db.get(Plan, catalog["plus"]["id"])
    assert (plan.trial_price, plan.second_price) == (20000, 35000)
    assert _count(db, RequestImage) == 2


# --- US3: the same person (T033, §6.1 row 2) ---------------------------------------------------


def test_known_national_id_is_a_missing_item_and_refuses(client, db, h, marketer, catalog):
    request_factory(db, marketer, national_id=NID, national_id_input="١٩٩٩١٢٣٤٥٦٧٨")
    db.commit()  # another marketer's submission, already committed
    draft_id = complete_draft(client, h, catalog, verified=False)
    draft = get_draft(client, h, draft_id)
    assert draft["checks"]["national_id_exists"] is True
    assert {"field": "national_id_exists", "code": "national_id_exists"} in draft["missing"]

    verify(client, h, draft_id)
    before = db.execute(text("SELECT last_value FROM request_number_seq")).scalar_one()
    res = submit(client, h, draft_id)

    assert (res.status_code, res.json()["code"]) == (409, "national_id_exists")
    assert res.json()["message"] == "المشترك لديه اشتراك سابق"
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    assert db.execute(text("SELECT last_value FROM request_number_seq")).scalar_one() == before
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "request.submit_refused")).one()
    assert entry.after == {"reason": "national_id_exists"}


def test_rejected_request_with_the_national_id_does_not_block(client, db, h, marketer, catalog):
    request_factory(db, marketer, national_id=NID, national_id_input=NID, status="rejected")
    assert submit(client, h, complete_draft(client, h, catalog)).json()["result"] == "approved"


# --- US4: the same family (T036, §6.1 row 3) ---------------------------------------------------


def _confirm(client, h, draft_id):
    return patch(client, h, draft_id, {"additional_confirmed": True})


def test_confirmed_family_is_an_additional_request_for_review(client, db, h, marketer, catalog):
    old = request_factory(db, marketer, family_number="1064 l00m 1234567890")
    draft_id = complete_draft(client, h, catalog, verified=False)
    assert get_draft(client, h, draft_id)["checks"]["family_exists"] is True
    assert _confirm(client, h, draft_id)["checks"]["additional_confirmed"] is True
    verify(client, h, draft_id)

    res = submit(client, h, draft_id)

    assert res.status_code == 201, res.json()
    body = res.json()
    assert (body["type"], body["status"], body["result"]) == (
        "additional",
        "pending_review",
        "pending_family",
    )
    assert body["reasons"] == ["family_exists"] and body["username"] is None
    rows = db.scalars(select(RequestReason).where(RequestReason.request_id == body["id"])).all()
    assert [(r.reason, r.matched_source, r.matched_ref) for r in rows] == [
        ("family_exists", "sijil", str(old.id))
    ]


def test_two_family_matches_make_two_rows(client, db, h, marketer, catalog):
    a = request_factory(db, marketer, family_number=FAMILY)
    b = request_factory(db, marketer, family_number=FAMILY.lower())
    draft_id = complete_draft(client, h, catalog, verified=False)
    _confirm(client, h, draft_id)
    verify(client, h, draft_id)
    body = submit(client, h, draft_id).json()
    refs = db.scalars(
        select(RequestReason.matched_ref).where(RequestReason.request_id == body["id"])
    ).all()
    assert sorted(refs) == sorted([str(a.id), str(b.id)])


def test_unconfirmed_family_refuses_as_incomplete(client, db, h, marketer, catalog):
    request_factory(db, marketer, family_number=FAMILY)
    draft_id = complete_draft(client, h, catalog, verified=False)
    verify(client, h, draft_id)
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (422, "draft_incomplete")
    assert res.json()["missing"] == [
        {"field": "family_exists_unconfirmed", "code": "family_exists_unconfirmed"}
    ]


# --- US5: edited numbers (T039, §6.1 row 4) ----------------------------------------------------


def _reasons(db, request_id):
    rows = db.scalars(select(RequestReason).where(RequestReason.request_id == request_id)).all()
    return [(r.reason, r.details) for r in rows]


def test_family_number_changed_from_the_reading_goes_to_review(client, db, h, catalog):
    draft_id = complete_draft(client, h, catalog, changes={"family_number": "1064L00M1234567891"})
    body = submit(client, h, draft_id).json()
    assert (body["status"], body["result"], body["reasons"]) == (
        "pending_review",
        "pending_review",
        ["numbers_edited"],
    )
    assert _reasons(db, body["id"]) == [("numbers_edited", {"fields": ["family_number"]})]


def test_only_a_name_edited_is_approved(client, db, h, catalog):
    draft_id = complete_draft(client, h, catalog, changes={"grandfather_name": "مختلف"})
    body = submit(client, h, draft_id).json()
    assert body["result"] == "approved"
    assert db.get(Request, body["id"]).card_fields["grandfather_name"]["source"] == "edited"


def test_numbers_typed_with_no_reading_go_to_review(client, db, h, catalog):
    draft_id = complete_draft(client, h, catalog, read_card=False)
    body = submit(client, h, draft_id).json()
    assert body["result"] == "pending_review"
    assert _reasons(db, body["id"]) == [
        ("numbers_edited", {"fields": ["national_id", "family_number"]})
    ]


def test_mrz_value_chosen_in_a_mismatch_is_approved(client, db, h, catalog):
    """The front reads NID, the back's verified MRZ another number; the marketer picks the MRZ."""
    from app.services.card_reader_fake_data import NID_OTHER

    draft_id = complete_draft(client, h, catalog, verified=False, back="back_nid_mismatch")
    out = patch(client, h, draft_id, {"national_id": NID_OTHER, "national_id_confirmed": True})
    assert not any(m["field"] == "national_id_unconfirmed" for m in out["missing"])
    verify(client, h, draft_id)
    body = submit(client, h, draft_id).json()
    assert body["result"] == "approved", body


def test_family_match_plus_edit_records_both(client, db, h, marketer, catalog):
    request_factory(db, marketer, family_number="1064L00M1234567891")
    draft_id = complete_draft(
        client, h, catalog, verified=False, changes={"family_number": "1064L00M1234567891"}
    )
    _confirm(client, h, draft_id)
    verify(client, h, draft_id)
    body = submit(client, h, draft_id).json()
    assert (body["type"], body["result"], body["reasons"]) == (
        "additional",
        "pending_family",
        ["family_exists", "numbers_edited"],
    )
