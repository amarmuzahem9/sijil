from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.timeutil import utc_now
from app.main import app
from app.models import UserSession
from app.services.auth_service import deactivate_user_sessions
from tests.conftest import auth_header, login


def _second_device(db) -> TestClient:
    """Another browser: its own cookie jar, same test database."""
    return TestClient(app, base_url="https://testserver")


def _sessions(db, user_id):
    return db.scalars(select(UserSession).where(UserSession.user_id == user_id)).all()


def test_logout_ends_only_this_device(client, db, make_user) -> None:
    user = make_user()
    login(client, user.phone)
    other = _second_device(db)
    login(other, user.phone)

    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    cleared = r.headers["set-cookie"].lower()
    assert cleared.startswith("sijil_refresh=") and "max-age=0" in cleared

    assert client.post("/api/auth/refresh").status_code == 401
    assert other.post("/api/auth/refresh").status_code == 200

    reasons = sorted(s.revoke_reason or "-" for s in _sessions(db, user.id))
    assert reasons == ["-", "logout"]


def test_logout_without_session_is_204(client) -> None:
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/logout").status_code == 204


def test_access_token_stops_working_after_logout(client, make_user) -> None:
    user = make_user()
    headers = auth_header(login(client, user.phone))
    client.post("/api/auth/logout")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401 and r.json()["code"] == "session_revoked"


def test_reused_refresh_token_revokes_session(client, db, make_user, frozen_clock) -> None:
    user = make_user()
    stolen = login(client, user.phone).cookies["sijil_refresh"]
    assert client.post("/api/auth/refresh").status_code == 200  # legitimate rotation

    frozen_clock.advance(timedelta(minutes=2))
    client.cookies.clear()
    client.cookies.set("sijil_refresh", stolen)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401 and r.json()["code"] == "session_revoked"

    (session,) = _sessions(db, user.id)
    assert session.revoke_reason == "reuse_detected" and session.revoked_at is not None


def test_second_tab_refresh_within_grace_is_allowed(client, make_user) -> None:
    user = make_user()
    first = login(client, user.phone).cookies["sijil_refresh"]
    assert client.post("/api/auth/refresh").status_code == 200
    client.cookies.clear()
    client.cookies.set("sijil_refresh", first)  # the other tab still holds the old cookie
    assert client.post("/api/auth/refresh").status_code == 200


def test_expired_session_is_refused(client, make_user, frozen_clock) -> None:
    user = make_user()
    login(client, user.phone)
    frozen_clock.advance(timedelta(days=30, seconds=1))
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401 and r.json()["code"] == "session_revoked"


def test_refresh_slides_expiry(client, db, make_user, frozen_clock) -> None:
    user = make_user()
    login(client, user.phone)
    frozen_clock.advance(timedelta(days=29))
    assert client.post("/api/auth/refresh").status_code == 200
    (session,) = _sessions(db, user.id)
    db.refresh(session)
    assert session.expires_at == utc_now() + timedelta(days=30)
    frozen_clock.advance(timedelta(days=29))
    assert client.post("/api/auth/refresh").status_code == 200  # 58 days after sign-in


def test_deactivation_takes_effect_on_next_request(client, db, make_user) -> None:
    user = make_user()
    headers = auth_header(login(client, user.phone))
    user.is_active = False
    db.flush()

    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "account_inactive"
    assert client.post("/api/auth/refresh").json()["code"] == "account_inactive"


def test_deactivate_user_sessions(client, db, make_user) -> None:
    user = make_user()
    other_user = make_user()
    for _ in range(2):
        login(_second_device(db), user.phone)
    login(client, other_user.phone)

    assert deactivate_user_sessions(db, user.id, "deactivated") == 2
    db.flush()
    assert {s.revoke_reason for s in _sessions(db, user.id)} == {"deactivated"}
    assert all(s.revoked_at is None for s in _sessions(db, other_user.id))
