"""The decision table with imported SAS subscribers (specs/015 US2: acceptance 1–5; FR-011–FR-014;
research R8, R14; docs/system.md 1.20 §12.2). A SAS subscriber has no national ID and no family
number, so a match is case 1, by the phone column or by the phone inside the username. The fake
card reader gives NID / FAMILY; SAS subscribers come from the helper. Synthetic data only."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Draft, Request, RequestReason
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for, pending_request
from tests.helpers.sas import sas_subscriber
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

# Values that must never reach the marketer (§3.1).
SAS_USERNAME = f"Zqx-99-{PHONE}"
SAS_NAME = "مشترك SAS سري"
SAS_ID = "SAS-ID-4242"
SAS_GROUP = "GROUP-SECRET"


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


def _sas(db, admin, **values):
    return sas_subscriber(
        db,
        admin,
        **(
            {
                "username": SAS_USERNAME,
                "full_name": SAS_NAME,
                "first_name": SAS_NAME,
                "last_name": None,
                "sas_id": SAS_ID,
                "group_name": SAS_GROUP,
            }
            | values
        ),
    )


def _reasons(db, request_id):
    return [
        (r.reason, r.matched_source, r.matched_ref, r.details)
        for r in db.scalars(
            select(RequestReason)
            .where(RequestReason.request_id == request_id)
            .order_by(RequestReason.id)
        )
    ]


def _leaks(*texts: str) -> list[str]:
    secrets = (SAS_USERNAME, SAS_USERNAME.upper(), SAS_NAME, SAS_ID, SAS_GROUP, "Zqx")
    return [s for s in secrets for text in texts if s in text]


# --- case 1 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("where", ["phone column", "username only"])
def test_a_sas_phone_is_case_1_on_the_draft(client, db, h, catalog, main_admin, where) -> None:
    if where == "phone column":
        _sas(db, main_admin, username="ZZT01-07709990000", phone=PHONE)
    else:
        _sas(db, main_admin, phone=None)  # the phone is only inside the username
    draft_id = complete_draft(client, h, catalog, verified=False)
    response = client.get(f"/api/drafts/{draft_id}", headers=h)
    checks = response.json()["checks"]
    assert (checks["phone_used"], checks["return_available"], checks["return_basis"]) == (
        True,
        True,
        "phone",
    )
    res = client.post(f"/api/drafts/{draft_id}/otp/send", headers=h)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")
    assert _leaks(response.text, res.text) == []


def test_a_sas_phone_refuses_a_new_request_and_keeps_the_draft(
    client, db, h, catalog, main_admin
) -> None:
    draft_id = complete_draft(client, h, catalog)  # verified before the import
    _sas(db, main_admin, phone=PHONE)
    res = submit(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (409, "phone_used")
    assert res.json()["message"] == "المشترك موجود سابقاً، هل يود العودة للخدمة؟"
    assert _leaks(res.text) == []
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    assert db.scalars(select(Request)).first() is None


def test_a_row_missing_from_the_last_file_still_blocks(client, db, h, catalog, main_admin) -> None:
    from app.core.timeutil import utc_now

    _sas(db, main_admin, phone=PHONE, missing_since=utc_now())
    draft = get_draft(client, h, complete_draft(client, h, catalog, verified=False))
    assert draft["checks"]["phone_used"] is True


# --- the return keeps the SAS username (§6.3 item 4, FR-013) ---------------------------------


def _return(client, h, catalog) -> dict:
    draft_id = complete_draft(client, h, catalog, verified=False)
    chosen = patch(client, h, draft_id, {"return_chosen": True})
    assert chosen["checks"]["phone_used"] is False
    verify(client, h, draft_id)
    res = submit(client, h, draft_id)
    assert res.status_code == 201, res.json()
    return res


def test_a_return_by_phone_keeps_the_sas_username_as_written(
    client, db, h, catalog, main_admin
) -> None:
    old = _sas(db, main_admin, phone=PHONE)
    res = _return(client, h, catalog)
    body = res.json()
    assert (body["type"], body["result"]) == ("return", "pending_approval")
    assert _reasons(db, body["id"]) == [("return", "sas", str(old.id), {"basis": "phone"})]
    assert db.get(Request, body["id"]).username == SAS_USERNAME
    # The marketer sees neither the username nor anything else of the SAS subscriber yet.
    assert _leaks(res.text) == []


def test_the_newest_sas_record_gives_the_username(client, db, h, catalog, main_admin) -> None:
    _sas(db, main_admin, username="Old-1-07709990001", phone=PHONE)
    newer = _sas(db, main_admin, username=f"New-2-{PHONE}", phone=None)
    res = _return(client, h, catalog)
    assert db.get(Request, res.json()["id"]).username == newer.username


def test_a_sijil_username_wins_over_a_sas_one(
    client, db, h, catalog, main_admin, make_user
) -> None:
    sijil = request_factory(db, make_user("marketer"), phone=PHONE, username="SIJ01-07801234567")
    _sas(db, main_admin, phone=PHONE)
    res = _return(client, h, catalog)
    assert db.get(Request, res.json()["id"]).username == sijil.username


def test_the_accepted_return_keeps_the_sas_username(
    client, db, h, catalog, main_admin, make_user
) -> None:
    _sas(db, main_admin, phone=PHONE)
    request_id = _return(client, h, catalog).json()["id"]
    reviewer = admin_with(make_user, "review")
    accepted = client.post(
        f"/api/admin/requests/{request_id}/accept",
        json={"counts_commission": True},
        headers=headers_for(client, reviewer),
    )
    assert accepted.status_code == 200, accepted.json()
    db.expire_all()
    request = db.get(Request, request_id)
    assert (request.status, request.username) == ("approved", SAS_USERNAME)


# --- what a SAS record never does --------------------------------------------------------------


def test_a_new_person_is_not_touched_by_sas_data(client, db, h, catalog, main_admin) -> None:
    _sas(db, main_admin, username="ZZT01-07709998877", phone="07709998866")
    res = submit(client, h, complete_draft(client, h, catalog))
    assert res.json()["result"] == "approved"


def test_the_review_recheck_after_a_pin_adds_nothing_for_a_sas_phone(
    client, db, make_user, main_admin
) -> None:
    """A SAS record holds no national ID or family number: the 010 re-check sees it (phone) but
    it never becomes a conflict or family row, and never a warning (review_check)."""
    marketer = make_user("marketer")
    request = pending_request(
        db,
        marketer,
        [("numbers_edited", None, {"fields": ["family_number"]})],
        phone=PHONE,
        card_fields={"family_number": {"original": "2222B0000000000002", "edited": True}},
    )
    _sas(db, main_admin, phone=PHONE)
    reviewer = admin_with(make_user, "review")
    res = client.post(
        f"/api/admin/requests/{request.id}/pin",
        json={"field": "family_number", "source": "reading"},
        headers=headers_for(client, reviewer),
    )
    assert res.status_code == 200, res.json()
    assert res.json()["type"] == "new"
    assert [s for _, s, _, _ in _reasons(db, request.id) if s == "sas"] == []
    file = client.get(f"/api/admin/requests/{request.id}", headers=headers_for(client, reviewer))
    assert file.json()["warnings"] == []
