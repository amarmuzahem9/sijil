"""US2 — managing marketers (specs/002 contracts/api.md › Marketers)."""

import pytest
from sqlalchemy import func, select

from app.models import AuditLog
from tests.conftest import TEST_PASSWORD, auth_header, login

TEMP = "Temp-Pass-123"
BASE = "/api/admin/marketers"


@pytest.fixture
def manager(client, make_user, db):
    a = make_user("admin")
    a.permissions = ["marketers"]
    db.flush()
    return auth_header(login(client, a.phone))


def _new(client, headers, phone="07700000201", name="مسوّق تجريبي"):
    r = client.post(
        BASE, json={"name": name, "phone": phone, "temporary_password": TEMP}, headers=headers
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _audit_count(db, user_id, action):
    return db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.entity_id == str(user_id), AuditLog.action == action)
    ).scalar_one()


def test_create_and_list(client, manager) -> None:
    m = _new(client, manager)
    assert m["role"] == "marketer" and m["must_change_password"] and m["permissions"] == []
    _new(client, manager, phone="07700000202", name="ب مسوّق")
    client.post(f"{BASE}/{m['id']}/deactivate", headers=manager)
    items = client.get(BASE, headers=manager).json()["items"]
    assert [i["is_active"] for i in items] == [True, False]  # active first


@pytest.mark.parametrize("role", ["super_admin"])
def test_main_admin_can_manage(client, make_user, role) -> None:
    h = auth_header(login(client, make_user(role).phone))
    assert client.get(BASE, headers=h).status_code == 200
    _new(client, h)


@pytest.mark.parametrize("perms", [[], ["review", "settings", "reports", "link", "commissions"]])
def test_admin_without_marketers_refused(client, make_user, db, perms) -> None:
    a = make_user("admin")
    a.permissions = perms
    db.flush()
    h = auth_header(login(client, a.phone))
    assert client.get(BASE, headers=h).status_code == 403
    r = client.post(
        BASE, json={"name": "مسوّق", "phone": "07700000203", "temporary_password": TEMP}, headers=h
    )
    assert r.status_code == 403


def test_marketer_refused(client, make_user) -> None:
    h = auth_header(login(client, make_user("marketer").phone))
    assert client.get(BASE, headers=h).status_code == 403


def test_admin_and_main_admin_unreachable(client, make_user, manager) -> None:
    for target in (make_user("admin"), make_user("super_admin")):
        for path in ("", "/deactivate", "/reactivate", "/reset-password"):
            method = client.patch if path == "" else client.post
            body = {"name": "x x"} if path == "" else {"temporary_password": TEMP}
            r = method(
                f"{BASE}/{target.id}{path}",
                json=body if path != "/deactivate" and path != "/reactivate" else None,
                headers=manager,
            )
            assert r.status_code == 404, (target.role, path)
        assert target.is_active


def test_permissions_field_rejected(client, manager) -> None:
    r = client.post(
        BASE,
        json={
            "name": "مسوّق",
            "phone": "07700000204",
            "temporary_password": TEMP,
            "permissions": ["review"],
        },
        headers=manager,
    )
    assert (r.status_code, r.json()["code"]) == (422, "validation_error")
    m = _new(client, manager)
    r = client.patch(f"{BASE}/{m['id']}", json={"permissions": ["review"]}, headers=manager)
    assert r.status_code == 422


def test_edit_name_phone_and_uniqueness(client, db, manager, make_user) -> None:
    m = _new(client, manager)
    other = make_user("admin", phone="07700000299")
    r = client.patch(f"{BASE}/{m['id']}", json={"phone": other.phone}, headers=manager)
    assert r.status_code == 409
    r = client.patch(f"{BASE}/{m['id']}", json={"phone": m["phone"]}, headers=manager)
    assert r.status_code == 200 and _audit_count(db, m["id"], "user.updated") == 0  # no-op
    r = client.patch(
        f"{BASE}/{m['id']}", json={"name": "اسم معدّل", "phone": "0770 000 0205"}, headers=manager
    )
    assert r.status_code == 200 and r.json()["phone"] == "07700000205"
    entry = db.execute(
        select(AuditLog).where(
            AuditLog.entity_id == str(m["id"]), AuditLog.action == "user.updated"
        )
    ).scalar_one()
    assert entry.before == {"name": "مسوّق تجريبي", "phone": "07700000201"}
    assert entry.after == {"name": "اسم معدّل", "phone": "07700000205"}


def test_phone_change_keeps_sessions(client, manager, make_user) -> None:
    mk = make_user("marketer", phone="07700000206")
    mh = auth_header(login(client, mk.phone))
    client.patch(f"{BASE}/{mk.id}", json={"phone": "07700000207"}, headers=manager)
    assert client.get("/api/marketer/dashboard", headers=mh).status_code == 200
    assert login(client, "07700000207").status_code == 200
    assert login(client, "07700000206").status_code == 401


def test_deactivate_ends_session_and_blocks_login(client, db, manager, make_user) -> None:
    mk = make_user("marketer")
    mh = auth_header(login(client, mk.phone))
    r = client.post(f"{BASE}/{mk.id}/deactivate", headers=manager)
    assert r.status_code == 200 and r.json()["is_active"] is False
    r = client.get("/api/marketer/dashboard", headers=mh)
    assert r.json() == {"code": "account_inactive", "message": "الحساب موقوف، راجع الإدارة"}
    r = client.post("/api/auth/refresh")  # the client's refresh cookie is the marketer's
    assert r.json()["code"] == "account_inactive"
    r = login(client, mk.phone)
    assert (r.status_code, r.json()["code"]) == (403, "account_inactive")
    client.post(f"{BASE}/{mk.id}/deactivate", headers=manager)  # no-op
    assert _audit_count(db, mk.id, "user.deactivated") == 1

    r = client.post(f"{BASE}/{mk.id}/reactivate", headers=manager)
    assert r.json()["is_active"] is True
    assert login(client, mk.phone, TEST_PASSWORD).status_code == 200
    assert (
        client.get("/api/marketer/dashboard", headers=mh).status_code == 401
    )  # old session stays dead
    assert _audit_count(db, mk.id, "user.reactivated") == 1


def test_reset_password(client, db, manager, make_user) -> None:
    mk = make_user("marketer")
    mh = auth_header(login(client, mk.phone))
    r = client.post(
        f"{BASE}/{mk.id}/reset-password", json={"temporary_password": "short"}, headers=manager
    )
    assert r.json()["code"] == "weak_password"
    r = client.post(
        f"{BASE}/{mk.id}/reset-password", json={"temporary_password": TEMP}, headers=manager
    )
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert client.get("/api/marketer/dashboard", headers=mh).status_code == 401
    assert login(client, mk.phone, TEST_PASSWORD).status_code == 401
    r = login(client, mk.phone, TEMP)
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is True
    assert _audit_count(db, mk.id, "user.password_reset") == 1
