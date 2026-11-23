"""The review file of one request (specs/010 US1: FR-003, FR-004, FR-012; contracts/api.md).
Synthetic data only: the fake card reader, made-up numbers, factory requests."""

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.core.timeutil import utc_now
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for, pending_request
from tests.helpers.submit import (
    complete_draft,
    make_catalog,
    marketer_headers,
    patch,
    submit,
    verify,
)

OLD_FAMILY = "7777C0000000000007"


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
def marketer(make_user):
    return make_user("marketer", name="مسوّق الملف")


@pytest.fixture
def review(client, make_user):
    return headers_for(client, admin_with(make_user, "review"))


@pytest.fixture
def submitted(client, db, make_user, marketer):
    """An end-to-end request: the marketer changed the family number from the reading to one an
    existing subscriber holds, then confirmed «إضافة اشتراك ثاني»."""
    catalog = make_catalog(client, headers_for(client, make_user("super_admin")))
    old = request_factory(db, make_user("marketer"), family_number=OLD_FAMILY, status="linked")
    h = marketer_headers(client, marketer)
    draft_id = complete_draft(
        client, h, catalog, changes={"family_number": OLD_FAMILY}, verified=False
    )
    patch(client, h, draft_id, {"additional_confirmed": True})
    verify(client, h, draft_id)
    res = submit(client, h, draft_id)
    assert res.status_code == 201, res.json()
    return res.json()["id"], old


def _file(client, headers, request_id):
    return client.get(f"/api/admin/requests/{request_id}", headers=headers)


def test_file_has_every_field(client, review, submitted, marketer) -> None:
    request_id, old = submitted

    res = _file(client, review, request_id)

    assert res.status_code == 200, res.json()
    body = res.json()
    assert (body["type"], body["status"]) == ("additional", "pending_review")
    assert body["marketer_name"] == "مسوّق الملف"
    assert body["national_id"] == NID
    assert body["family_number"] == OLD_FAMILY
    assert body["names"]["first_name"] and body["full_name"]
    assert {i["side"] for i in body["images"]} == {"front", "back"}
    assert body["location"]["lat"] == pytest.approx(34.70)
    assert (body["address"], body["landmark"]) == ("حي تجريبي", "قرب نقطة تجريبية")
    assert (body["tower_code"], body["plan_name"]) == ("ALM03", "PLUS")
    assert (body["trial_price"], body["second_price"]) == (20000, 35000)
    assert body["phone"] == "07801234567" and body["otp_verified_at"]
    assert body["username"] == "ALM03-07801234567"
    assert body["warnings"] == []
    assert body["decision"] is None


def test_numbers_show_reading_mrz_marketer_and_current(client, review, submitted) -> None:
    request_id, _ = submitted
    numbers = _file(client, review, request_id).json()["numbers"]

    assert numbers["family_number"] == {
        "reading": FAMILY,
        "mrz": None,
        "marketer": OLD_FAMILY,
        "current": OLD_FAMILY,
        "edited": True,
        "pins": [],
    }
    nid = numbers["national_id"]
    assert (nid["reading"], nid["mrz"], nid["marketer"], nid["current"]) == (NID, NID, NID, NID)
    assert nid["edited"] is False


def test_names_reading_comes_from_the_card(client, review, submitted) -> None:
    request_id, _ = submitted
    body = _file(client, review, request_id).json()
    assert body["names_reading"]["first_name"] == body["names"]["first_name"]


def test_reasons_carry_state_and_the_linked_record(client, review, submitted) -> None:
    request_id, old = submitted
    reasons = _file(client, review, request_id).json()["reasons"]

    family = next(r for r in reasons if r["reason"] == "family_exists")
    assert (family["state"], family["added_at_review"], family["basis"]) == ("open", False, None)
    record = family["record"]
    assert (record["source"], record["ref"], record["available"]) == ("sijil", str(old.id), True)
    assert (record["full_name"], record["username"]) == (old.full_name, old.username)
    assert (record["phone"], record["status"]) == (old.phone, "linked")
    assert record["expiry"] is None
    edited = next(r for r in reasons if r["reason"] == "numbers_edited")
    assert (edited["fields"], edited["record"]) == (["family_number"], None)


def test_return_rows_carry_their_basis(client, db, review, marketer) -> None:
    old = request_factory(db, marketer)
    request = pending_request(db, marketer, [("return", old, {"basis": "phone"})], type="return")
    (reason,) = _file(client, review, request.id).json()["reasons"]
    assert (reason["reason"], reason["basis"]) == ("return", "phone")
    assert reason["record"]["ref"] == str(old.id)


def test_never_returns_card_readings(client, review, submitted) -> None:
    request_id, _ = submitted
    text = json.dumps(_file(client, review, request_id).json())
    assert "card_readings" not in text
    assert '"raw"' not in text and "detections" not in text


def test_decided_requests_show_their_decision(client, db, review, marketer, make_user) -> None:
    auto = request_factory(db, marketer, status="approved")
    decision = _file(client, review, auto.id).json()["decision"]
    assert (decision["status"], decision["by"]) == ("approved", None)

    admin = make_user("super_admin", name="أدمن القرار")
    rejected = request_factory(
        db,
        marketer,
        status="rejected",
        rejected_by=admin.id,
        rejection_reason="other",
        rejection_note="طلب مكرر",
    )
    decision = _file(client, review, rejected.id).json()["decision"]
    assert (decision["status"], decision["by"]) == ("rejected", "أدمن القرار")
    assert (decision["reason"], decision["label"]) == ("other", "طلب مكرر")


def test_archived_marketer_request_is_still_shown(client, db, review, make_user) -> None:
    gone = make_user("marketer", name="مسوّق مؤرشف")
    request = pending_request(db, gone, [("numbers_edited", None, {"fields": ["national_id"]})])
    archiver = make_user("super_admin")
    gone.is_active = False
    gone.archived_at = utc_now()
    gone.archived_by = archiver.id
    db.flush()

    res = _file(client, review, request.id)
    assert res.status_code == 200
    assert res.json()["marketer_name"] == "مسوّق مؤرشف"


@pytest.mark.parametrize("who", ["settings_admin", "marketer"])
def test_others_get_404(client, db, make_user, marketer, who) -> None:
    request = pending_request(db, marketer, [("numbers_edited", None, {"fields": []})])
    user = admin_with(make_user, "settings") if who == "settings_admin" else marketer
    res = _file(client, headers_for(client, user), request.id)
    assert res.status_code == 404
    assert res.json()["code"] == "request_not_found"


def test_missing_id_is_404(client, review) -> None:
    assert _file(client, review, 999999).status_code == 404
