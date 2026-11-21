from datetime import timedelta

from sqlalchemy import select

from app.core.timeutil import utc_now
from app.models import AuditLog
from tests.conftest import login

WRONG = "definitely-wrong"


def test_fifth_failure_locks_for_15_minutes(client, db, make_user, frozen_clock) -> None:
    user = make_user()
    for _ in range(4):
        assert login(client, user.phone, WRONG).status_code == 401
    fifth = login(client, user.phone, WRONG)
    assert fifth.status_code == 423 and fifth.json()["code"] == "account_locked"

    db.refresh(user)
    assert user.locked_until == utc_now() + timedelta(minutes=15)
    assert user.failed_logins == 0
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "user.locked")).one()
    assert audit.entity_id == str(user.id) and audit.actor_id is None


def test_locked_account_refuses_correct_password(client, make_user, frozen_clock) -> None:
    user = make_user()
    for _ in range(5):
        login(client, user.phone, WRONG)
    frozen_clock.advance(timedelta(minutes=5))

    r = login(client, user.phone)
    assert r.status_code == 423
    body = r.json()
    assert body["code"] == "account_locked"
    assert body["retry_after_seconds"] == 600 and r.headers["retry-after"] == "600"
    assert "10 دقائق" in body["message"]


def test_sign_in_works_after_lock_expires(client, make_user, frozen_clock) -> None:
    user = make_user()
    for _ in range(5):
        login(client, user.phone, WRONG)
    frozen_clock.advance(timedelta(minutes=15))
    assert login(client, user.phone).status_code == 200


def test_success_resets_counter(client, db, make_user) -> None:
    user = make_user()
    for _ in range(3):
        login(client, user.phone, WRONG)
    assert login(client, user.phone).status_code == 200
    db.refresh(user)
    assert user.failed_logins == 0
    for _ in range(4):
        assert login(client, user.phone, WRONG).status_code == 401  # not locked yet


def test_invalid_phone_changes_no_counter(client, db, make_user) -> None:
    user = make_user()
    for _ in range(6):
        assert login(client, "12345", WRONG).status_code == 422
    db.refresh(user)
    assert user.failed_logins == 0 and user.locked_until is None


def test_per_ip_limit(client) -> None:
    # Default LOGIN_IP_LIMIT = 20 failed attempts per 15 minutes per client IP.
    for i in range(20):
        assert login(client, f"0770900{i:04d}", WRONG).status_code == 401
    r = login(client, "07709000099", WRONG)
    assert r.status_code == 429 and r.json()["code"] == "too_many_attempts"
    assert int(r.headers["retry-after"]) > 0


def test_per_ip_limit_window_slides(client, frozen_clock) -> None:
    for i in range(20):
        login(client, f"0770900{i:04d}", WRONG)
    frozen_clock.advance(timedelta(minutes=15))
    assert login(client, "07709000099", WRONG).status_code == 401
