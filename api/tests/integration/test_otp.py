"""Phone OTP (specs/007): send and verify (US1), cancellation on context change (US2).

Fake sender only: the code is read from its in-memory outbox. Synthetic phones and names.
"""

import uuid

import pytest
from sqlalchemy import select

from app.errors import AppError
from app.models import Draft, OtpChallenge
from app.services import otp_service
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login

SETTINGS = "/api/admin/settings"
PHONE = "07801234567"


# --- fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def fake():
    sender = get_otp_sender()
    sender.outbox.clear()
    sender.fail_with = None
    sender.wait_minutes = None
    yield sender
    sender.outbox.clear()
    sender.fail_with = None


@pytest.fixture
def admin(client, make_user):
    return auth_header(login(client, make_user("super_admin").phone))


def _marketer_headers(client, make_user):
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


@pytest.fixture
def h(client, make_user):
    return _marketer_headers(client, make_user)


@pytest.fixture
def catalog(client, admin):
    alam = client.post(f"{SETTINGS}/areas", json={"name": "العلم"}, headers=admin).json()
    samra = client.post(f"{SETTINGS}/areas", json={"name": "سمرة"}, headers=admin).json()

    def tower(code, area):
        return client.post(
            f"{SETTINGS}/towers",
            json={"code": code, "name": f"برج {code}", "area_id": area["id"]},
            headers=admin,
        ).json()

    def plan(name, trial, second):
        return client.post(
            f"{SETTINGS}/plans",
            json={"name": name, "trial_price": trial, "second_price": second},
            headers=admin,
        ).json()

    return {
        "alam": alam,
        "samra": samra,
        "alm01": tower("ALM01", alam),
        "alm02": tower("ALM02", alam),
        "smr01": tower("SMR01", samra),
        "plus": plan("PLUS", 20000, 35000),
        "max": plan("MAX", 30000, 45000),
    }


def _draft(client, h, catalog, phone=PHONE):
    draft_id = str(uuid.uuid4())
    changes = {
        "area_id": catalog["alam"]["id"],
        "tower_id": catalog["alm01"]["id"],
        "plan_id": catalog["plus"]["id"],
        "phone_input": phone,
    }
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": changes}, headers=h)
    assert res.status_code == 201, res.json()
    return draft_id, res.json()


def _send(client, h, draft_id):
    return client.post(f"/api/drafts/{draft_id}/otp/send", headers=h)


def _verify(client, h, draft_id, code):
    return client.post(f"/api/drafts/{draft_id}/otp/verify", json={"code": code}, headers=h)


def _patch(client, h, draft_id, changes):
    version = client.get(f"/api/drafts/{draft_id}", headers=h).json()["version"]
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": version, "changes": changes}, headers=h
    )
    assert res.status_code == 200, res.json()
    return res.json()


def _verified_draft(client, h, catalog, fake):
    draft_id, _ = _draft(client, h, catalog)
    assert _send(client, h, draft_id).status_code == 200
    res = _verify(client, h, draft_id, fake.outbox[-1][1])
    assert res.status_code == 200, res.json()
    assert res.json()["otp"]["status"] == "verified"
    return draft_id


# --- US1: send ----------------------------------------------------------------------------------


def test_send_creates_one_challenge_and_hides_the_code(client, db, h, catalog, fake) -> None:
    draft_id, _ = _draft(client, h, catalog, phone="٠٧٨٠ ١٢٣ ٤٥٦٧")

    res = _send(client, h, draft_id)

    assert res.status_code == 200, res.json()
    ((phone, code),) = fake.outbox
    assert phone == PHONE and len(code) == 6 and code.isdigit()
    otp = res.json()["otp"]
    assert otp["status"] == "sent"
    assert otp["phone"] == PHONE
    assert otp["attempts_left"] == 3
    assert otp["resend_at"] and otp["expires_at"]
    assert code not in res.text
    rows = db.execute(select(OtpChallenge)).scalars().all()
    assert len(rows) == 1
    assert rows[0].request_id == uuid.UUID(draft_id)
    assert rows[0].phone == PHONE
    assert code not in (rows[0].code_hash, rows[0].context_hash)


def test_get_draft_shows_the_pending_code_state(client, h, catalog, fake) -> None:
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    body = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    assert body["otp"]["status"] == "sent"


@pytest.mark.parametrize("phone", ["0780123", "", "12345678901"])
def test_invalid_or_empty_phone_sends_nothing(client, db, h, catalog, fake, phone) -> None:
    draft_id, _ = _draft(client, h, catalog, phone=phone)
    res = _send(client, h, draft_id)
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_phone"
    assert fake.outbox == []
    assert db.execute(select(OtpChallenge)).first() is None


def test_new_draft_has_no_otp_state(client, h, catalog) -> None:
    _, body = _draft(client, h, catalog)
    assert body["otp"] == {
        "status": "none",
        "phone": None,
        "resend_at": None,
        "expires_at": None,
        "attempts_left": None,
        "verified_at": None,
    }


# --- US1: verify --------------------------------------------------------------------------------


def test_right_code_verifies_and_records_the_time(client, db, h, catalog, fake) -> None:
    draft_id, created = _draft(client, h, catalog)
    _send(client, h, draft_id)
    code = fake.outbox[-1][1]
    arabic = code.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))

    res = _verify(client, h, draft_id, f"{arabic[:3]} {arabic[3:]}")

    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["otp"]["status"] == "verified"
    assert body["otp"]["verified_at"]
    assert body["version"] == created["version"] + 1
    draft = db.get(Draft, uuid.UUID(draft_id))
    assert draft.otp_verified_at is not None
    assert draft.otp_context_hash == otp_service.context_hash(draft)
    challenge = db.execute(select(OtpChallenge)).scalar_one()
    assert challenge.verified_at == draft.otp_verified_at
    assert code not in res.text


def test_verified_state_is_seen_from_another_device(client, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    other_device = {**h, "X-Client-Id": str(uuid.uuid4())}
    body = client.get(f"/api/drafts/{draft_id}", headers=other_device).json()
    assert body["otp"]["status"] == "verified"


def test_send_when_already_verified_is_refused(client, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    res = _send(client, h, draft_id)
    assert res.status_code == 409
    assert res.json()["code"] == "otp_already_verified"
    assert len(fake.outbox) == 1


def test_verify_without_a_code_sent(client, h, catalog) -> None:
    draft_id, _ = _draft(client, h, catalog)
    res = _verify(client, h, draft_id, "123456")
    assert res.status_code == 409
    assert res.json()["code"] == "otp_no_active"


# --- US1: access and the 008 hook -----------------------------------------------------------------


def test_another_marketers_draft_is_404(client, make_user, h, catalog, fake) -> None:
    draft_id, _ = _draft(client, h, catalog)
    other = _marketer_headers(client, make_user)
    assert _send(client, other, draft_id).status_code == 404
    assert _verify(client, other, draft_id, "123456").status_code == 404
    assert fake.outbox == []


def test_admin_cannot_send(client, admin, h, catalog, fake) -> None:
    draft_id, _ = _draft(client, h, catalog)
    res = _send(client, {**admin, "X-Client-Id": str(uuid.uuid4())}, draft_id)
    assert res.status_code == 403


def test_precheck_refusal_stops_the_send(client, db, h, catalog, fake, monkeypatch) -> None:
    seen = []

    def refuse(db_, draft, phone):
        seen.append(phone)
        return AppError("phone_taken", 409)

    monkeypatch.setattr(otp_service, "precheck_for_otp", refuse)
    draft_id, _ = _draft(client, h, catalog)

    res = _send(client, h, draft_id)

    assert seen == [PHONE]
    assert res.status_code == 409 and res.json()["code"] == "phone_taken"
    assert fake.outbox == []
    assert db.execute(select(OtpChallenge)).first() is None


# --- US2: a change after verification cancels it --------------------------------------------------


def _assert_cancelled(db, body, draft_id) -> None:
    assert body["otp"]["status"] == "needs_reverify"
    draft = db.get(Draft, uuid.UUID(draft_id))
    db.refresh(draft)
    assert draft.otp_verified_at is None
    assert draft.otp_context_hash is None


def test_phone_change_cancels(client, db, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    _assert_cancelled(db, _patch(client, h, draft_id, {"phone_input": "07801234568"}), draft_id)


def test_tower_change_cancels(client, db, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    body = _patch(client, h, draft_id, {"tower_id": catalog["alm02"]["id"]})
    _assert_cancelled(db, body, draft_id)


def test_area_change_cancels_through_the_tower(client, db, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    body = _patch(client, h, draft_id, {"area_id": catalog["samra"]["id"]})
    assert body["tower_id"] is None
    _assert_cancelled(db, body, draft_id)


def test_category_change_cancels(client, db, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    _assert_cancelled(db, _patch(client, h, draft_id, {"plan_id": catalog["max"]["id"]}), draft_id)


@pytest.mark.parametrize("field,value", [("trial_price", 22000), ("second_price", 40000)])
def test_admin_price_change_cancels_at_next_save(
    client, db, h, admin, catalog, fake, field, value
) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    res = client.patch(
        f"{SETTINGS}/plans/{catalog['plus']['id']}", json={field: value}, headers=admin
    )
    assert res.status_code == 200, res.json()

    body = _patch(client, h, draft_id, {"address": "حي تجريبي"})

    assert body[field] == value
    _assert_cancelled(db, body, draft_id)


@pytest.mark.parametrize("same", ["0780 123 4567", "٠٧٨٠١٢٣٤٥٦٧", "+964 780 123 4567"])
def test_same_normalized_phone_keeps_verification(client, h, catalog, fake, same) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    body = _patch(client, h, draft_id, {"phone_input": same})
    assert body["otp"]["status"] == "verified"


def test_other_fields_keep_verification(client, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    body = _patch(client, h, draft_id, {"address": "حي تجريبي", "first_name": "مشترك"})
    assert body["otp"]["status"] == "verified"


def test_putting_the_old_value_back_stays_cancelled(client, db, h, catalog, fake) -> None:
    draft_id = _verified_draft(client, h, catalog, fake)
    _patch(client, h, draft_id, {"plan_id": catalog["max"]["id"]})
    body = _patch(client, h, draft_id, {"plan_id": catalog["plus"]["id"]})
    _assert_cancelled(db, body, draft_id)


def test_reverify_after_cancel(client, h, catalog, fake, frozen_clock) -> None:
    from datetime import timedelta

    draft_id = _verified_draft(client, h, catalog, fake)
    _patch(client, h, draft_id, {"plan_id": catalog["max"]["id"]})
    frozen_clock.advance(timedelta(seconds=61))
    assert _send(client, h, draft_id).status_code == 200
    res = _verify(client, h, draft_id, fake.outbox[-1][1])
    assert res.json()["otp"]["status"] == "verified"


def test_phone_change_cancels_a_pending_code(client, h, catalog, fake) -> None:
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    code = fake.outbox[-1][1]

    body = _patch(client, h, draft_id, {"phone_input": "07801234568"})

    assert body["otp"]["status"] == "none"
    res = _verify(client, h, draft_id, code)
    assert res.status_code == 409
    assert res.json()["code"] == "otp_no_active"


def test_category_change_cancels_a_pending_code(client, h, catalog, fake) -> None:
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    code = fake.outbox[-1][1]
    _patch(client, h, draft_id, {"plan_id": catalog["max"]["id"]})
    assert _verify(client, h, draft_id, code).json()["code"] == "otp_no_active"
