"""The decision table with imported legacy subscribers (specs/014 US2: acceptance 1, 2, 4, 6, 7;
FR-012, FR-013, FR-021; docs/system.md §6.1 notes). The fake card reader gives NID / FAMILY;
legacy subscribers come from the helper. Synthetic data only."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Draft, Request, RequestReason
from app.services.card_reader_fake_data import FAMILY
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.review import admin_with, headers_for, pending_request
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
def main_admin(make_user):
    return make_user("super_admin")


@pytest.fixture
def catalog(client, main_admin):
    return make_catalog(client, auth_header(login(client, main_admin.phone)))


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, marketer):
    return marketer_headers(client, marketer)


def _reasons(db, request_id):
    return [
        (r.reason, r.matched_source, r.matched_ref, r.details)
        for r in db.scalars(
            select(RequestReason)
            .where(RequestReason.request_id == request_id)
            .order_by(RequestReason.id)
        )
    ]


# --- case 1: the phone of a legacy subscriber ------------------------------------------------


def test_a_legacy_phone_is_case_1_on_the_draft(client, db, h, catalog, main_admin) -> None:
    legacy_subscriber(db, main_admin, phone=PHONE)
    draft = get_draft(client, h, complete_draft(client, h, catalog, verified=False))
    checks = draft["checks"]
    assert (checks["phone_used"], checks["return_available"], checks["return_basis"]) == (
        True,
        True,
        "phone",
    )
    res = client.post(f"/api/drafts/{draft['id']}/otp/send", headers=h)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")


def test_a_legacy_phone_refuses_a_new_request_and_keeps_the_draft(
    client, db, h, catalog, main_admin
) -> None:
    draft_id = complete_draft(client, h, catalog)  # verified before the import
    legacy_subscriber(db, main_admin, phone=PHONE)
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")
    assert res.json()["message"] == "المشترك موجود سابقاً، هل يود العودة للخدمة؟"
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    assert db.scalars(select(Request)).first() is None


def test_a_return_by_phone_to_a_legacy_subscriber_gets_a_new_username(
    client, db, h, catalog, main_admin
) -> None:
    old = legacy_subscriber(db, main_admin, phone=PHONE)
    draft_id = complete_draft(client, h, catalog, verified=False)
    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["phone_used"] is False
    verify(client, h, draft_id)
    res = submit(client, h, draft_id)
    assert res.status_code == 201, res.json()
    assert (res.json()["type"], res.json()["result"]) == ("return", "pending_approval")
    assert _reasons(db, res.json()["id"]) == [("return", "legacy", str(old.id), {"basis": "phone"})]
    request = db.get(Request, res.json()["id"])
    assert request.username == f"{catalog['alm03']['code']}-{PHONE}"  # FR-013


# --- case 3: the family number of a legacy subscriber ----------------------------------------


def test_a_legacy_family_number_is_a_second_subscription(
    client, db, h, catalog, main_admin
) -> None:
    old = legacy_subscriber(db, main_admin, family_number=FAMILY.lower().replace("0", "o"))
    draft_id = complete_draft(client, h, catalog, verified=False)
    checks = get_draft(client, h, draft_id)["checks"]
    assert (checks["family_exists"], checks["national_id_exists"]) == (True, False)
    patch(client, h, draft_id, {"additional_confirmed": True})
    verify(client, h, draft_id)
    res = submit(client, h, draft_id)
    assert res.status_code == 201, res.json()
    body = res.json()
    assert (body["type"], body["status"], body["result"]) == (
        "additional",
        "pending_review",
        "pending_family",
    )
    assert [(r, s, ref) for r, s, ref, _ in _reasons(db, body["id"])] == [
        ("family_exists", "legacy", str(old.id))
    ]


def test_the_review_recheck_after_a_pin_finds_a_legacy_family(
    client, db, make_user, main_admin
) -> None:
    old = legacy_subscriber(db, main_admin, family_number="2222B0000000000001")
    marketer = make_user("marketer")
    request = pending_request(
        db,
        marketer,
        [("numbers_edited", None, {"fields": ["family_number"]})],
        card_fields={"family_number": {"original": "2222B0000000000001", "edited": True}},
    )
    reviewer = admin_with(make_user, "review")
    res = client.post(
        f"/api/admin/requests/{request.id}/pin",
        json={"field": "family_number", "source": "reading"},
        headers=headers_for(client, reviewer),
    )
    assert res.status_code == 200, res.json()
    assert res.json()["type"] == "additional"
    assert ("family_exists", "legacy", str(old.id)) in [
        (r, s, ref) for r, s, ref, _ in _reasons(db, request.id)
    ]


# --- rows that do not count, and new data --------------------------------------------------


@pytest.mark.parametrize("status", ["ملغي", "مرفوض"])
def test_a_cancelled_or_refused_legacy_row_changes_nothing(
    client, db, h, catalog, main_admin, status
) -> None:
    legacy_subscriber(db, main_admin, phone=PHONE, family_number=FAMILY, status_text=status)
    draft_id = complete_draft(client, h, catalog)
    res = submit(client, h, draft_id)
    assert res.status_code == 201, res.json()
    assert res.json()["result"] == "approved"


def test_a_new_person_is_not_touched_by_legacy_data(client, db, h, catalog, main_admin) -> None:
    legacy_subscriber(db, main_admin, phone="07809998877", family_number="7777C0000000000007")
    res = submit(client, h, complete_draft(client, h, catalog))
    assert res.json()["result"] == "approved"
