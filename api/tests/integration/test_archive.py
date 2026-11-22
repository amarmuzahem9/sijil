"""Feature 003: account archive (specs/003 contracts/api.md, docs/system.md §3.6)."""

import pytest
from sqlalchemy import func, select

from app.core.access import ADMIN_PERMISSIONS
from app.models import AuditLog, UserSession
from tests.conftest import TEST_PASSWORD, auth_header, login

BASE = "/api/admin/archive"


@pytest.fixture
def main(make_user):
    return make_user("super_admin", name="المدير")


@pytest.fixture
def h(client, main):
    return auth_header(login(client, main.phone))


def _count(db, user_id, action):
    return db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.entity_id == str(user_id), AuditLog.action == action)
    ).scalar_one()


# --- US1: archive ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "active"), [("marketer", True), ("admin", True), ("marketer", False)]
)
def test_archive_ends_sessions_and_blocks_login(client, db, h, make_user, role, active) -> None:
    target = make_user(role)
    th = auth_header(login(client, target.phone))
    if not active:
        target.is_active = False
        db.flush()

    r = client.post(f"{BASE}/{target.id}", headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    db.refresh(target)
    assert target.archived_at is not None

    assert client.get("/api/auth/me", headers=th).json()["code"] == "account_inactive"
    r = login(client, target.phone)
    assert r.json() == {"code": "account_inactive", "message": "الحساب موقوف، راجع الإدارة"}
    reasons = {
        s.revoke_reason
        for s in db.execute(select(UserSession).where(UserSession.user_id == target.id)).scalars()
    }
    assert reasons == {"archived"}
    assert _count(db, target.id, "user.archived") == 1


def test_archived_leaves_lists_and_002_routes(client, db, h, make_user) -> None:
    m, a = make_user("marketer"), make_user("admin")
    for u in (m, a):
        client.post(f"{BASE}/{u.id}", headers=h)
    assert m.id not in {
        x["id"] for x in client.get("/api/admin/marketers", headers=h).json()["items"]
    }
    assert a.id not in {x["id"] for x in client.get("/api/admin/admins", headers=h).json()["items"]}
    for kind, u in (("marketers", m), ("admins", a)):
        assert (
            client.patch(f"/api/admin/{kind}/{u.id}", json={"name": "س س"}, headers=h).status_code
            == 404
        )
        for action in ("deactivate", "reactivate"):
            assert client.post(f"/api/admin/{kind}/{u.id}/{action}", headers=h).status_code == 404
        r = client.post(
            f"/api/admin/{kind}/{u.id}/reset-password",
            json={"temporary_password": "Temp-Pass-123"},
            headers=h,
        )
        assert r.status_code == 404


def test_main_admin_never_archived(client, db, main, h, make_user) -> None:
    other_main = make_user("super_admin")
    for target in (main, other_main):
        assert client.post(f"{BASE}/{target.id}", headers=h).status_code == 404
        db.refresh(target)
        assert target.archived_at is None and target.is_active


def test_double_archive_and_unknown_are_404(client, db, h, make_user) -> None:
    m = make_user("marketer")
    assert client.post(f"{BASE}/{m.id}", headers=h).status_code == 200
    assert client.post(f"{BASE}/{m.id}", headers=h).status_code == 404
    assert client.post(f"{BASE}/999999999", headers=h).status_code == 404
    assert _count(db, m.id, "user.archived") == 1


@pytest.mark.parametrize("role", ["admin", "marketer"])
def test_only_main_admin_can_use_archive(client, db, make_user, role) -> None:
    caller = make_user(role)
    if role == "admin":
        caller.permissions = list(ADMIN_PERMISSIONS)
        db.flush()
    ch = auth_header(login(client, caller.phone))
    target = make_user("marketer")
    assert client.post(f"{BASE}/{target.id}", headers=ch).status_code == 403
    assert client.get(BASE, headers=ch).status_code == 403
    assert client.post(f"{BASE}/{target.id}/restore", headers=ch).status_code == 403
    db.refresh(target)
    assert target.archived_at is None


# --- US2: list and restore -------------------------------------------------------------------


def test_list_newest_first_with_archiver(client, h, make_user, frozen_clock) -> None:
    from datetime import timedelta

    first, second = make_user("marketer", name="الأول"), make_user("admin", name="الثاني")
    client.post(f"{BASE}/{first.id}", headers=h)
    frozen_clock.advance(timedelta(minutes=5))
    client.post(f"{BASE}/{second.id}", headers=h)
    items = client.get(BASE, headers=h).json()["items"]
    assert [i["id"] for i in items] == [second.id, first.id]
    assert items[0]["archived_by"]["name"] == "المدير" and items[0]["role"] == "admin"
    assert items[0]["archived_at"].endswith(("Z", "+00:00"))


def test_restore_returns_deactivated_and_keeps_fields(client, db, h, make_user) -> None:
    a = make_user("admin", must_change_password=True)
    a.permissions = ["review", "marketers"]
    db.flush()
    client.post(f"{BASE}/{a.id}", headers=h)

    r = client.post(f"{BASE}/{a.id}/restore", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["is_active"] is False and body["permissions"] == ["review", "marketers"]
    assert body["must_change_password"] is True
    assert a.id in {x["id"] for x in client.get("/api/admin/admins", headers=h).json()["items"]}
    assert a.id not in {x["id"] for x in client.get(BASE, headers=h).json()["items"]}
    assert login(client, a.phone).json()["code"] == "account_inactive"

    assert client.post(f"/api/admin/admins/{a.id}/reactivate", headers=h).status_code == 200
    assert login(client, a.phone, TEST_PASSWORD).status_code == 200
    assert _count(db, a.id, "user.restored") == 1
    assert client.post(f"{BASE}/{a.id}/restore", headers=h).status_code == 404  # not archived


# --- US3: history and phone ------------------------------------------------------------------


def test_archived_phone_stays_reserved(client, h, make_user) -> None:
    m = make_user("marketer", phone="07700000301")
    other = make_user("marketer")
    client.post(f"{BASE}/{m.id}", headers=h)
    body = {"name": "مسوّق آخر", "phone": "+964 770 000 0301", "temporary_password": "Temp-Pass-123"}
    assert client.post("/api/admin/marketers", json=body, headers=h).json()["code"] == "phone_taken"
    r = client.patch(f"/api/admin/marketers/{other.id}", json={"phone": m.phone}, headers=h)
    assert r.json()["code"] == "phone_taken"


def test_history_keeps_the_name(client, db, h, make_user) -> None:
    a = make_user("admin", name="أدمن مؤرشف")
    a.permissions = ["marketers"]
    db.flush()
    ah = auth_header(login(client, a.phone))
    created = client.post(
        "/api/admin/marketers",
        headers=ah,
        json={"name": "مسوّق قديم", "phone": "07700000302", "temporary_password": "Temp-Pass-123"},
    ).json()
    client.post(f"{BASE}/{a.id}", headers=h)

    entries = client.get("/api/admin/audit", params={"actor_id": a.id}, headers=h).json()["items"]
    assert any(
        e["target"]["id"] == created["id"] and e["actor"]["name"] == "أدمن مؤرشف" for e in entries
    )
    archived = client.get("/api/admin/audit", headers=h).json()["items"][0]
    assert archived["action"] == "user.archived" and archived["target"]["name"] == "أدمن مؤرشف"
    assert archived["before"] == {"is_active": True, "archived": False}
    assert archived["after"] == {"is_active": False, "archived": True}
    actors = client.get("/api/admin/audit/actors", headers=h).json()["items"]
    assert a.id in {x["id"] for x in actors}
