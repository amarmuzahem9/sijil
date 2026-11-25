"""`python -m app.cli go-live` (specs/016 FR-022, research R11, T061). Synthetic accounts only.

Run once by the operator before APP_ENV=production: the demo and e2e accounts made by
`seed-demo` are deactivated (never deleted, constitution III), their sessions end, and the step
is audited. `go-live --check` tells deploy.sh whether any demo account is still active.
"""

import pytest
from sqlalchemy import select

from app.cli import DEMO_ACCOUNTS, E2E_ACCOUNTS, go_live, go_live_check, seed_demo
from app.config import get_settings
from app.core.timeutil import utc_now
from app.models import AuditLog, User, UserSession

DEMO_PHONES = [phone for _, phone, _ in DEMO_ACCOUNTS + E2E_ACCOUNTS]


def _settings():
    base = get_settings().model_dump()
    return type(get_settings()).model_construct(
        **(base | {"app_env": "staging", "demo_marketer_password": "Demo-Passw0rd"})
    )


@pytest.fixture
def demo(db):
    assert seed_demo(db, _settings(), e2e=True) == 0
    return list(db.scalars(select(User).where(User.phone.in_(DEMO_PHONES))))


def test_deactivates_the_demo_accounts_and_ends_their_sessions(db, demo, make_user) -> None:
    real = make_user("marketer", phone="07812345678", name="مسوّق حقيقي تجريبي")
    db.add(
        UserSession(
            user_id=demo[0].id,
            refresh_token_hash="synthetic-hash",
            expires_at=utc_now(),
        )
    )
    db.flush()

    assert go_live(db) == 0

    for user in demo:
        db.refresh(user)
        assert user.is_active is False
    assert db.get(User, real.id).is_active is True  # nobody else is touched
    assert db.scalar(select(User).where(User.phone == DEMO_PHONES[0])) is not None  # not deleted
    session = db.scalar(select(UserSession).where(UserSession.user_id == demo[0].id))
    assert session.revoked_at is not None
    entry = db.scalar(select(AuditLog).where(AuditLog.action == "system.go_live"))
    assert entry.actor_id is None
    assert entry.after == {"deactivated": len(DEMO_PHONES)}


def test_is_idempotent(db, demo) -> None:
    assert go_live(db) == 0
    assert go_live(db) == 0
    entries = list(db.scalars(select(AuditLog).where(AuditLog.action == "system.go_live")))
    assert [e.after for e in entries] == [{"deactivated": len(DEMO_PHONES)}, {"deactivated": 0}]


def test_check_reports_active_demo_accounts(db, demo) -> None:
    assert go_live_check(db) == 1
    go_live(db)
    assert go_live_check(db) == 0


def test_check_without_any_demo_account(db) -> None:
    assert go_live_check(db) == 0
