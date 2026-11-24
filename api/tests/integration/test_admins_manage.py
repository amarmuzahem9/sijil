"""US3 — main admin edits, deactivates, reactivates and resets admins (specs/002)."""

import pytest
from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import TEST_PASSWORD, auth_header, login

TEMP = "Temp-Pass-123"
BASE = "/api/admin/admins"


@pytest.fixture
def boss(client, make_user):
    return auth_header(login(client, make_user("super_admin").phone))


def _actions(db, user_id):
    return [
        e.action
        for e in db.execute(
            select(AuditLog).where(AuditLog.entity_id == str(user_id)).order_by(AuditLog.id)
        ).scalars()
    ]


def _admin(make_user, db, perms):
    a = make_user("admin")
    a.permissions = perms
    db.flush()
    return a


def test_permission_change_applies_to_existing_token(client, db, boss, make_user) -> None:
    a = _admin(make_user, db, ["marketers"])
    ah = auth_header(login(client, a.phone))
    assert client.get("/api/admin/marketers", headers=ah).status_code == 200

    r = client.patch(f"{BASE}/{a.id}", json={"permissions": ["settings"]}, headers=boss)
    assert r.status_code == 200 and r.json()["permissions"] == ["settings"]
    assert client.get("/api/admin/marketers", headers=ah).status_code == 403  # same token

    entry = db.execute(
        select(AuditLog).where(
            AuditLog.entity_id == str(a.id), AuditLog.action == "user.permissions_changed"
        )
    ).scalar_one()
    assert entry.before == {"permissions": ["marketers"]}
    assert entry.after == {"permissions": ["settings"]}


def test_name_and_permissions_together_write_two_entries(client, db, boss, make_user) -> None:
    a = _admin(make_user, db, [])
    r = client.patch(
        f"{BASE}/{a.id}", json={"name": "أدمن معدّل", "permissions": ["review"]}, headers=boss
    )
    assert r.status_code == 200
    assert _actions(db, a.id) == ["user.updated", "user.permissions_changed"]


def test_deactivate_reactivate_reset(client, db, boss, make_user) -> None:
    a = _admin(make_user, db, ["review"])
    ah = auth_header(login(client, a.phone))

    assert client.post(f"{BASE}/{a.id}/deactivate", headers=boss).json()["is_active"] is False
    assert client.get("/api/admin/ping", headers=ah).json()["code"] == "account_inactive"
    assert login(client, a.phone).json()["code"] == "account_inactive"

    assert client.post(f"{BASE}/{a.id}/reactivate", headers=boss).json()["is_active"] is True
    ah = auth_header(login(client, a.phone, TEST_PASSWORD))
    assert client.get("/api/admin/ping", headers=ah).status_code == 200

    r = client.post(
        f"{BASE}/{a.id}/reset-password", json={"temporary_password": TEMP}, headers=boss
    )
    assert r.json()["must_change_password"] is True
    assert client.get("/api/admin/ping", headers=ah).status_code == 401
    assert login(client, a.phone, TEMP).json()["user"]["must_change_password"] is True
    assert _actions(db, a.id) == ["user.deactivated", "user.reactivated", "user.password_reset"]


def test_main_admin_unreachable(client, db, make_user) -> None:
    main = make_user("super_admin")
    h = auth_header(login(client, main.phone))
    calls = [
        ("patch", "", {"permissions": []}),
        ("patch", "", {"name": "اسم آخر"}),
        ("post", "/deactivate", None),
        ("post", "/reactivate", None),
        ("post", "/reset-password", {"temporary_password": TEMP}),
    ]
    for method, path, body in calls:
        r = getattr(client, method)(f"{BASE}/{main.id}{path}", json=body, headers=h)
        assert r.status_code == 404, (method, path)
    db.refresh(main)
    assert main.is_active and main.permissions == [] and main.role == "super_admin"
    assert _actions(db, main.id) == []


def test_marketer_ids_unreachable(client, boss, make_user) -> None:
    m = make_user("marketer")
    assert client.post(f"{BASE}/{m.id}/deactivate", headers=boss).status_code == 404


@pytest.mark.parametrize(
    "perms", [["marketers"], ["review", "link", "settings", "marketers", "reports", "commissions"]]
)
def test_admins_cannot_manage_admins(client, db, make_user, perms) -> None:
    target = _admin(make_user, db, [])
    caller = _admin(make_user, db, perms)
    h = auth_header(login(client, caller.phone))
    assert client.patch(f"{BASE}/{target.id}", json={"name": "س س"}, headers=h).status_code == 403
    assert client.post(f"{BASE}/{target.id}/deactivate", headers=h).status_code == 403
    # Not even on themselves (spec edge case).
    r = client.patch(f"{BASE}/{caller.id}", json={"permissions": []}, headers=h)
    assert r.status_code == 403
    assert client.post(f"{BASE}/{caller.id}/deactivate", headers=h).status_code == 403


# --- specs/011 T034: the «حذف مشترك» permission --------------------------------------------------


def test_main_admin_gives_and_removes_delete(client, db, boss) -> None:
    body = {
        "name": "أدمن حذف تجريبي",
        "phone": "07700000177",
        "temporary_password": TEMP,
        "permissions": ["delete", "review"],
    }
    r = client.post(BASE, json=body, headers=boss)
    assert r.status_code == 201, r.json()
    admin_id = r.json()["id"]
    assert r.json()["permissions"] == ["review", "delete"]

    r = client.patch(f"{BASE}/{admin_id}", json={"permissions": ["review"]}, headers=boss)
    assert r.status_code == 200 and r.json()["permissions"] == ["review"]
    entry = db.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == str(admin_id), AuditLog.action == "user.permissions_changed"
        )
    ).one()
    assert entry.before == {"permissions": ["review", "delete"]}
    assert entry.after == {"permissions": ["review"]}


def test_a_marketer_cannot_hold_delete(db, make_user) -> None:
    from sqlalchemy.exc import IntegrityError

    marketer = make_user("marketer")
    marketer.permissions = ["delete"]
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_main_admin_holds_delete_without_a_stored_permission(client, db, make_user) -> None:
    """The main admin's permissions stay empty in the database; it holds `delete` implicitly
    (has_any_permission), so its request files offer «حذف»."""
    from tests.helpers.requests import request_factory

    main = make_user("super_admin")
    request = request_factory(db, make_user("marketer"), status="pending_review")
    h = auth_header(login(client, main.phone))
    assert main.permissions == []
    assert client.get(f"/api/admin/requests/{request.id}", headers=h).json()["can_delete"] is True
