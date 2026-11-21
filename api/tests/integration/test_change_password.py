from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import TEST_PASSWORD, auth_header, login

NEW_PASSWORD = "Brand-New-Passw0rd"


def test_forced_user_is_confined_until_change(client, db, make_user) -> None:
    user = make_user("super_admin", must_change_password=True)
    r = login(client, user.phone)
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is True
    headers = auth_header(r)

    blocked = client.get("/api/admin/ping", headers=headers)
    assert blocked.status_code == 403 and blocked.json()["code"] == "password_change_required"
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    changed = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    body = changed.json()
    assert body["user"]["must_change_password"] is False and body["access_token"]
    assert "sijil_refresh=" in changed.headers["set-cookie"]

    assert client.get("/api/admin/ping", headers=auth_header(changed)).status_code == 200

    audit = db.scalars(select(AuditLog).where(AuditLog.action == "user.password_changed")).one()
    assert audit.actor_id == user.id
    assert audit.before == {"must_change_password": True}
    assert audit.after == {"must_change_password": False}
    dumped = str(audit.before) + str(audit.after)
    assert NEW_PASSWORD not in dumped and TEST_PASSWORD not in dumped and "hash" not in dumped

    # Old password no longer works, new one does.
    assert login(client, user.phone).status_code == 401
    assert login(client, user.phone, NEW_PASSWORD).status_code == 200


def test_change_requires_correct_current_password(client, make_user) -> None:
    user = make_user(must_change_password=True)
    r = client.post(
        "/api/auth/change-password",
        headers=auth_header(login(client, user.phone)),
        json={"current_password": "wrong-one", "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 400 and r.json()["code"] == "wrong_current_password"


def _change(client, headers, current, new):
    return client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": current, "new_password": new},
    )


def test_flagged_marketer_is_confined(client, make_user) -> None:
    user = make_user("marketer", must_change_password=True)
    headers = auth_header(login(client, user.phone))
    r = client.get("/api/marketer/dashboard", headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "password_change_required"
    changed = _change(client, headers, TEST_PASSWORD, NEW_PASSWORD)
    assert changed.status_code == 200
    assert client.get("/api/marketer/dashboard", headers=auth_header(changed)).status_code == 200


def test_password_rules(client, make_user) -> None:
    user = make_user(must_change_password=True)
    headers = auth_header(login(client, user.phone))
    weak = _change(client, headers, TEST_PASSWORD, "short")
    assert weak.status_code == 422 and weak.json() == {
        "code": "weak_password",
        "message": "كلمة السر يجب أن تكون 8 أحرف على الأقل",
    }
    same = _change(client, headers, TEST_PASSWORD, TEST_PASSWORD)
    assert same.status_code == 422 and same.json()["code"] == "same_password"
    wrong = _change(client, headers, "not-current-1", NEW_PASSWORD)
    assert wrong.status_code == 400 and wrong.json()["code"] == "wrong_current_password"


def test_voluntary_change_revokes_other_sessions(client, db, make_user) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    user = make_user("marketer")
    other = TestClient(app, base_url="https://testserver")
    other_headers = auth_header(login(other, user.phone))

    changed = _change(client, auth_header(login(client, user.phone)), TEST_PASSWORD, NEW_PASSWORD)
    assert changed.status_code == 200
    # This device keeps working; the other device is signed out.
    assert client.get("/api/auth/me", headers=auth_header(changed)).status_code == 200
    assert client.post("/api/auth/refresh").status_code == 200
    assert other.get("/api/auth/me", headers=other_headers).json()["code"] == "session_revoked"
    assert other.post("/api/auth/refresh").status_code == 401

    audit = db.scalars(
        select(AuditLog).where(
            AuditLog.action == "user.password_changed", AuditLog.entity_id == str(user.id)
        )
    ).one()
    assert set(audit.before) | set(audit.after) == {"must_change_password"}


def test_change_password_needs_auth(client) -> None:
    r = client.post(
        "/api/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert r.status_code == 401
