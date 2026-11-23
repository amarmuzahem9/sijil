"""Phone OTP limits and failures (specs/007 US3, US4; research R6, R7; quickstart table).

The owner's list: expiry, 3 attempts, hourly limit, and a failed send is not counted. Plus the
60 s resend wait and two parallel sends. Fake sender and the `utc_now` override only.
"""

# The shared OTP fixtures are imported from test_otp; pytest injects them by argument name.
# ruff: noqa: F811

import threading
import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.timeutil import utc_now
from app.models import Draft, OtpChallenge, User
from app.services import otp_service
from app.services.otp_sender import FakeOtpSender, SendReceipt
from tests.conftest import auth_header, login
from tests.integration.test_otp import (  # noqa: F401 - fixtures
    PHONE,
    _draft,
    _send,
    _verify,
    admin,
    catalog,
    fake,
)

SETTINGS = "/api/admin/settings"


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def headers(client, marketer):
    """Fresh headers on every call: moving the clock past 15 min expires the access token."""

    def make(client_id: str = str(uuid.uuid4())) -> dict[str, str]:
        h = auth_header(login(client, marketer.phone))
        h["X-Client-Id"] = client_id
        return h

    return make


def _rows(db, phone: str = PHONE) -> list[OtpChallenge]:
    return list(db.execute(select(OtpChallenge).where(OtpChallenge.phone == phone)).scalars())


# --- expiry -----------------------------------------------------------------------------------


def test_code_expires_after_the_setting(client, headers, catalog, fake, frozen_clock) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    code = fake.outbox[-1][1]

    frozen_clock.advance(timedelta(minutes=60, seconds=1))
    res = _verify(client, headers(), draft_id, code)

    assert res.status_code == 410
    assert res.json()["code"] == "otp_expired"
    assert res.json()["message"] == "انتهت صلاحية الرمز، اطلب رمزاً جديداً"


def test_code_valid_just_before_expiry(client, headers, catalog, fake, frozen_clock) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    frozen_clock.advance(timedelta(minutes=59, seconds=59))
    res = _verify(client, headers(), draft_id, fake.outbox[-1][1])
    assert res.status_code == 200, res.json()


def test_setting_change_does_not_move_a_sent_codes_expiry(
    client, admin, headers, catalog, fake, frozen_clock
) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    res = client.patch(f"{SETTINGS}/general", json={"otp_validity_minutes": 10}, headers=admin)
    assert res.status_code == 200, res.json()

    frozen_clock.advance(timedelta(minutes=30))
    assert _verify(client, headers(), draft_id, fake.outbox[-1][1]).status_code == 200


def test_new_setting_applies_to_the_next_code(client, admin, headers, catalog, fake, frozen_clock):
    client.patch(f"{SETTINGS}/general", json={"otp_validity_minutes": 10}, headers=admin)
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    body = _send(client, h, draft_id).json()
    frozen_clock.advance(timedelta(minutes=10, seconds=1))
    assert _verify(client, headers(), draft_id, fake.outbox[-1][1]).json()["code"] == "otp_expired"
    assert body["otp"]["expires_at"]


# --- three attempts ---------------------------------------------------------------------------


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def test_three_wrong_attempts_cancel_the_code(client, headers, catalog, fake) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    code = fake.outbox[-1][1]

    first = _verify(client, h, draft_id, _wrong(code))
    assert (first.status_code, first.json()["code"]) == (422, "otp_wrong")
    assert first.json()["attempts_left"] == 2
    assert first.json()["message"] == "الرمز غير صحيح، بقيت محاولتان"
    assert client.get(f"/api/drafts/{draft_id}", headers=h).json()["otp"]["attempts_left"] == 2

    second = _verify(client, h, draft_id, _wrong(code))
    assert second.json()["attempts_left"] == 1
    assert second.json()["message"] == "الرمز غير صحيح، بقيت محاولة واحدة"

    third = _verify(client, h, draft_id, _wrong(code))
    assert (third.status_code, third.json()["code"]) == (410, "otp_cancelled")

    # Even the right code no longer works, and the page leaves the code box.
    after = _verify(client, h, draft_id, code)
    assert after.status_code == 410
    assert after.json()["code"] == "otp_cancelled"
    assert client.get(f"/api/drafts/{draft_id}", headers=h).json()["otp"]["status"] == "none"


@pytest.mark.parametrize("entry", ["12345", "1234567", "abcdef", ""])
def test_malformed_entry_does_not_use_an_attempt(client, db, headers, catalog, fake, entry) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    res = _verify(client, h, draft_id, entry)
    assert (res.status_code, res.json()["code"]) == (422, "otp_code_format")
    assert _rows(db)[0].attempts == 0


# --- resend wait ------------------------------------------------------------------------------


def test_resend_waits_60_seconds_and_replaces_the_code(
    client, headers, catalog, fake, frozen_clock
) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    _send(client, h, draft_id)
    old = fake.outbox[-1][1]

    frozen_clock.advance(timedelta(seconds=40))
    early = _send(client, h, draft_id)
    assert (early.status_code, early.json()["code"]) == (429, "otp_resend_wait")
    assert early.json()["retry_after_s"] == 20
    assert early.json()["message"] == "إعادة الإرسال بعد 20 ثانية"
    assert len(fake.outbox) == 1

    frozen_clock.advance(timedelta(seconds=20))
    assert _send(client, h, draft_id).status_code == 200
    new = fake.outbox[-1][1]

    if old != new:  # a random code may repeat (1 in a million)
        stale = _verify(client, h, draft_id, old)
        assert stale.json()["code"] == "otp_wrong"
    assert _verify(client, h, draft_id, new).status_code == 200


# --- hourly limit -----------------------------------------------------------------------------


def test_five_codes_per_phone_per_hour_across_drafts(
    client, db, headers, catalog, fake, frozen_clock
) -> None:
    start = utc_now()
    h = headers()
    first, _ = _draft(client, h, catalog)
    second, _ = _draft(client, h, catalog)
    for i in range(5):
        res = _send(client, h, first if i % 2 == 0 else second)
        assert res.status_code == 200, (i, res.json())
        frozen_clock.advance(timedelta(seconds=61))

    sixth = _send(client, h, second)
    assert (sixth.status_code, sixth.json()["code"]) == (429, "otp_hourly_limit")
    # The oldest send leaves the window 60 min after `start`; now is start + 5 × 61 s.
    assert sixth.json()["retry_after_min"] == 55
    assert sixth.json()["message"] == (
        "وصلت الحد الأقصى (5 رموز في الساعة) لهذا الرقم، حاول بعد 55 دقيقة"
    )
    assert len(fake.outbox) == 5

    frozen_clock.set(start + timedelta(minutes=60, seconds=1))
    assert _send(client, headers(), second).status_code == 200
    assert len(_rows(db)) == 6


def test_another_phone_is_not_limited(client, headers, catalog, fake, frozen_clock) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    for _ in range(5):
        _send(client, h, draft_id)
        frozen_clock.advance(timedelta(seconds=61))
    other, _ = _draft(client, h, catalog, phone="07801234568")
    assert _send(client, h, other).status_code == 200


def test_deleted_drafts_still_count(client, db, headers, catalog, fake, frozen_clock) -> None:
    h = headers()
    for _ in range(5):
        draft_id, _ = _draft(client, h, catalog)
        assert _send(client, h, draft_id).status_code == 200
        assert client.delete(f"/api/drafts/{draft_id}", headers=h).status_code == 204
        frozen_clock.advance(timedelta(seconds=61))

    rows = _rows(db)
    assert len(rows) == 5
    assert all(row.request_id is None for row in rows)
    draft_id, _ = _draft(client, h, catalog)
    assert _send(client, h, draft_id).json()["code"] == "otp_hourly_limit"


# --- failed sends (US4) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason,status,code",
    [
        ("not_configured", 503, "otp_not_configured"),
        ("no_credit", 502, "otp_no_credit"),
        ("rejected", 502, "otp_rejected"),
        ("unavailable", 502, "otp_unavailable"),
        ("busy", 429, "otp_provider_busy"),
    ],
)
def test_failed_send_is_not_counted(client, db, headers, catalog, fake, reason, status, code):
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    fake.fail_with = reason

    res = _send(client, h, draft_id)

    assert (res.status_code, res.json()["code"]) == (status, code)
    assert _rows(db) == []
    # No 60 s wait after a failure: the next send goes through at once.
    fake.fail_with = None
    assert _send(client, h, draft_id).status_code == 200


def test_provider_busy_gives_its_minutes(client, headers, catalog, fake) -> None:
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    fake.fail_with, fake.wait_minutes = "busy", 8
    res = _send(client, h, draft_id)
    assert res.json()["retry_after_min"] == 8
    assert res.json()["message"] == "حاول بعد 8 دقيقة"


def test_failures_do_not_use_the_hourly_limit(client, db, headers, catalog, fake, frozen_clock):
    h = headers()
    draft_id, _ = _draft(client, h, catalog)
    for _ in range(5):
        fake.fail_with = "unavailable"
        assert _send(client, h, draft_id).status_code == 502
        fake.fail_with = None
        assert _send(client, h, draft_id).status_code == 200
        frozen_clock.advance(timedelta(seconds=61))
    assert len(_rows(db)) == 5
    assert len(fake.outbox) == 5


def test_no_key_refuses_but_the_draft_still_saves(client, headers, catalog, monkeypatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "otp_mode", "otpiq")
    monkeypatch.setattr(settings, "otpiq_api_key", "")
    h = headers()
    draft_id, created = _draft(client, h, catalog)

    res = _send(client, h, draft_id)
    assert (res.status_code, res.json()["code"]) == (503, "otp_not_configured")
    saved = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": created["version"], "changes": {"address": "حي تجريبي"}},
        headers=h,
    )
    assert saved.status_code == 200


# --- two sends at once ------------------------------------------------------------------------


class _SlowSender(FakeOtpSender):
    """Holds the draft and phone locks long enough for the other thread to wait on them."""

    def send(self, phone: str, code: str) -> SendReceipt:
        time.sleep(0.4)
        return super().send(phone, code)


@pytest.fixture
def committed_draft(engine):
    """A real committed user and draft: two connections must both see them."""
    with Session(engine) as s:
        user = User(
            name="مسوّق التزامن",
            phone="07719999001",
            password_hash=hash_password("Test-Passw0rd"),
            role="marketer",
            permissions=[],
        )
        s.add(user)
        s.flush()
        draft = Draft(id=uuid.uuid4(), marketer_id=user.id, phone_input=PHONE)
        draft.phone_normalized = PHONE
        s.add(draft)
        s.commit()
        ids = (user.id, draft.id)
    yield ids
    with Session(engine) as s:
        s.execute(delete(OtpChallenge).where(OtpChallenge.request_id == ids[1]))
        s.execute(delete(Draft).where(Draft.id == ids[1]))
        s.execute(delete(User).where(User.id == ids[0]))
        s.commit()


def test_two_parallel_sends_make_one_code(engine, committed_draft) -> None:
    user_id, draft_id = committed_draft
    sender = _SlowSender()
    results: list[str] = []

    def attempt() -> None:
        with Session(engine) as s:
            user = s.get(User, user_id)
            try:
                otp_service.send(s, user, draft_id, sender)
                results.append("ok")
            except Exception as err:  # AppError
                results.append(getattr(err, "code", type(err).__name__))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == ["ok", "otp_resend_wait"]
    assert len(sender.outbox) == 1
    with Session(engine) as s:
        count = len(
            s.execute(select(OtpChallenge).where(OtpChallenge.request_id == draft_id)).all()
        )
    assert count == 1
