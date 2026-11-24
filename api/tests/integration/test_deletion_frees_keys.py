"""After «حذف مشترك» the phone, the national ID and the family number are free again, the phone's
OTP limit starts again, and the next request gets a new number (specs/011 US2: FR-010, FR-013,
FR-014; research R1, R5). Synthetic data only."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.core.family_key import family_key
from app.models import Request
from app.services import match_service
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import add_otp_rows, request_factory
from tests.helpers.submit import (
    PHONE,
    complete_draft,
    get_draft,
    make_catalog,
    marketer_headers,
    send_code,
    submit,
    verify,
)


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    get_otp_sender().outbox.clear()
    return tmp_path


@pytest.fixture
def owner(make_user):
    return make_user("super_admin")


@pytest.fixture
def catalog(client, owner):
    return make_catalog(client, auth_header(login(client, owner.phone)))


@pytest.fixture
def me(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, me):
    return marketer_headers(client, me)


def _the_same_person(db, marketer) -> Request:
    """A pending request holding the phone, the national ID and the family number that the fake
    reader and `complete_draft` will use, with the phone's 5 codes of the hour already spent."""
    request = request_factory(
        db,
        marketer,
        status="pending_review",
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
    )
    add_otp_rows(db, PHONE, 5)
    return request


def _delete(client, owner, request) -> None:
    res = client.post(
        f"/api/admin/requests/{request.id}/delete",
        json={"reason": "duplicate", "confirm_number": request.number_label},
        headers=auth_header(login(client, owner.phone)),
    )
    assert res.status_code == 200, res.json()


def test_keys_are_taken_before_and_free_after(client, db, h, me, owner, catalog) -> None:
    old = _the_same_person(db, me)
    draft_id = complete_draft(client, h, catalog, verified=False)

    # Before: the phone is used (a used phone is refused before the hourly limit is counted).
    assert get_draft(client, h, draft_id)["checks"]["phone_used"] is True
    assert send_code(client, h, draft_id).json()["code"] == "phone_used"

    _delete(client, owner, old)

    # After: the same draft goes through as a new subscriber. The phone had spent its 5 codes of
    # the hour, so the code below is sent only because the deletion removed them (R5).
    assert get_draft(client, h, draft_id)["checks"]["phone_used"] is False
    out = verify(client, h, draft_id)
    assert out["missing"] == [], out["missing"]
    res = submit(client, h, draft_id)
    assert res.status_code in (200, 201), res.json()
    created = res.json()
    assert (created["type"], created["result"]) == ("new", "approved")
    # The number is never reused.
    assert created["number"] > old.number
    top = db.scalar(select(func.max(Request.number)))
    assert created["number"] == top


def test_no_check_matches_a_deleted_request(client, db, me, owner) -> None:
    old = _the_same_person(db, me)
    _delete(client, owner, old)

    found = match_service.find_matches(
        db, phone=PHONE, national_id=NID, family_key=family_key(FAMILY)
    )
    assert [r for r in found.records if r.ref.ref_id == str(old.id)] == []
