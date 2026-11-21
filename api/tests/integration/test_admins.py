"""US1 — main admin adds an admin (specs/002 contracts/api.md › Admins)."""

import pytest
from sqlalchemy import select

from app.core.access import ADMIN_PERMISSIONS
from app.models import AuditLog
from tests.conftest import auth_header, login

TEMP = "Temp-Pass-123"


@pytest.fixture
def boss_headers(client, make_user):
    return auth_header(login(client, make_user("super_admin").phone))


def _body(phone="07700000101", **extra):
    return {
        "name": "أدمن تجريبي",
        "phone": phone,
        "temporary_password": TEMP,
        "permissions": ["marketers"],
        **extra,
    }


def test_create_admin(client, db, boss_headers) -> None:
    r = client.post("/api/admin/admins", json=_body(), headers=boss_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "admin" and body["permissions"] == ["marketers"]
    assert body["must_change_password"] is True and body["is_active"] is True
    assert set(body) == {
        "id",
        "name",
        "phone",
        "role",
        "permissions",
        "is_active",
        "must_change_password",
        "created_at",
    }  # never a password or hash
    entry = db.execute(
        select(AuditLog).where(
            AuditLog.action == "user.created", AuditLog.entity_id == str(body["id"])
        )
    ).scalar_one()
    assert entry.after["permissions"] == ["marketers"]

    listed = client.get("/api/admin/admins", headers=boss_headers).json()["items"]
    assert [a["phone"] for a in listed] == ["07700000101"]


def test_new_admin_must_change_password(client, boss_headers) -> None:
    client.post("/api/admin/admins", json=_body(), headers=boss_headers)
    r = login(client, "07700000101", TEMP)
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is True
    assert client.get("/api/admin/ping", headers=auth_header(r)).json()["code"] == (
        "password_change_required"
    )


def test_duplicate_phone_any_format(client, boss_headers, make_user) -> None:
    make_user("marketer", phone="07700000102")
    r = client.post(
        "/api/admin/admins", json=_body(phone="+964 770 000 0102"), headers=boss_headers
    )
    assert r.status_code == 409
    assert r.json() == {"code": "phone_taken", "message": "رقم الهاتف مستخدم لحساب آخر"}


@pytest.mark.parametrize(
    ("override", "status", "code"),
    [
        ({"permissions": ["review", "root"]}, 422, "validation_error"),
        ({"name": "ا"}, 422, "invalid_name"),
        ({"temporary_password": "short"}, 422, "weak_password"),
        ({"phone": "0123"}, 422, "invalid_phone"),
        ({"role": "super_admin"}, 422, "validation_error"),
    ],
)
def test_create_admin_validation(client, boss_headers, override, status, code) -> None:
    r = client.post("/api/admin/admins", json=_body(**override), headers=boss_headers)
    assert (r.status_code, r.json()["code"]) == (status, code)


def test_all_switches_off_allowed(client, boss_headers) -> None:
    r = client.post("/api/admin/admins", json=_body(permissions=[]), headers=boss_headers)
    assert r.status_code == 201 and r.json()["permissions"] == []


@pytest.mark.parametrize("perms", [[], list(ADMIN_PERMISSIONS)])
def test_admins_cannot_manage_admins(client, make_user, db, perms) -> None:
    a = make_user("admin")
    a.permissions = perms
    db.flush()
    h = auth_header(login(client, a.phone))
    assert client.get("/api/admin/admins", headers=h).status_code == 403
    assert client.post("/api/admin/admins", json=_body(), headers=h).status_code == 403


def test_marketer_cannot_manage_admins(client, make_user) -> None:
    h = auth_header(login(client, make_user("marketer").phone))
    assert client.get("/api/admin/admins", headers=h).status_code == 403
