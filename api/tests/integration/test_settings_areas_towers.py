"""US1 — regions and towers (specs/004 contracts/api.md, docs/system.md §10 v1.3)."""

import pytest
from sqlalchemy import select, text

from app.core.access import ADMIN_PERMISSIONS
from app.models import AuditLog, Tower
from app.services import settings_service
from tests.conftest import auth_header, login

BASE = "/api/admin/settings"


@pytest.fixture
def h(client, make_user, db):
    """An admin holding only `settings`."""
    a = make_user("admin")
    a.permissions = ["settings"]
    db.flush()
    return auth_header(login(client, a.phone))


def _actions(db, entity_type, item_id):
    rows = db.execute(
        select(AuditLog.action)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(item_id))
        .order_by(AuditLog.id)
    ).scalars()
    return list(rows)


def _area(client, h, name="العلم"):
    r = client.post(f"{BASE}/areas", json={"name": name}, headers=h)
    assert r.status_code == 201, r.json()
    return r.json()


def _tower(client, h, area_id, code="ALM01", name="العلم 1"):
    r = client.post(
        f"{BASE}/towers", json={"code": code, "name": name, "area_id": area_id}, headers=h
    )
    assert r.status_code == 201, r.json()
    return r.json()


# --- permission -------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["super_admin"])
def test_main_admin_passes(client, make_user, role) -> None:
    h = auth_header(login(client, make_user(role).phone))
    assert client.get(f"{BASE}/areas", headers=h).status_code == 200


def test_refused_without_settings(client, make_user, db) -> None:
    a = make_user("admin")
    a.permissions = [p for p in ADMIN_PERMISSIONS if p != "settings"]
    db.flush()
    m = make_user("marketer")
    for user in (a, m):
        hh = auth_header(login(client, user.phone))
        calls = [
            client.get(f"{BASE}/areas", headers=hh),
            client.post(f"{BASE}/areas", json={"name": "منطقة"}, headers=hh),
            client.get(f"{BASE}/towers", headers=hh),
            client.post(
                f"{BASE}/towers", json={"code": "AB1", "name": "x", "area_id": 1}, headers=hh
            ),
            client.patch(f"{BASE}/areas/1", json={"name": "س"}, headers=hh),
            client.post(f"{BASE}/areas/1/deactivate", headers=hh),
            client.delete(f"{BASE}/towers/1", headers=hh),
        ]
        assert {r.status_code for r in calls} == {403}, user.role


# --- areas ------------------------------------------------------------------------------------


def test_area_create_rename_state_and_audit(client, db, h) -> None:
    area = _area(client, h)
    assert area == {
        "id": area["id"],
        "name": "العلم",
        "is_active": True,
        "in_use": False,
        "tower_count": 0,
    }

    r = client.post(f"{BASE}/areas", json={"name": "  العلم  "}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "name_taken")
    r = client.post(f"{BASE}/areas", json={"name": "   "}, headers=h)
    assert (r.status_code, r.json()["code"]) == (422, "invalid_name")

    r = client.patch(f"{BASE}/areas/{area['id']}", json={"name": "العلم"}, headers=h)  # no-op
    assert r.status_code == 200
    r = client.patch(f"{BASE}/areas/{area['id']}", json={"name": "العلم   الجديدة"}, headers=h)
    assert r.json()["name"] == "العلم الجديدة"

    assert (
        client.post(f"{BASE}/areas/{area['id']}/deactivate", headers=h).json()["is_active"] is False
    )
    client.post(f"{BASE}/areas/{area['id']}/deactivate", headers=h)  # no-op
    assert (
        client.post(f"{BASE}/areas/{area['id']}/reactivate", headers=h).json()["is_active"] is True
    )
    assert _actions(db, "area", area["id"]) == [
        "area.created",
        "area.updated",
        "area.deactivated",
        "area.reactivated",
    ]


def test_area_with_towers_cannot_be_deleted(client, db, h) -> None:
    area = _area(client, h)
    _tower(client, h, area["id"])
    listed = next(
        a for a in client.get(f"{BASE}/areas", headers=h).json()["items"] if a["id"] == area["id"]
    )
    assert listed["in_use"] is True and listed["tower_count"] == 1
    r = client.delete(f"{BASE}/areas/{area['id']}", headers=h)
    assert r.json() == {"code": "item_in_use", "message": "العنصر مستعمل، يمكن إيقافه فقط"}


def test_unused_area_is_deleted_and_audited(client, db, h) -> None:
    area = _area(client, h, "منطقة مؤقتة")
    assert client.delete(f"{BASE}/areas/{area['id']}", headers=h).status_code == 204
    assert all(
        a["id"] != area["id"] for a in client.get(f"{BASE}/areas", headers=h).json()["items"]
    )
    deleted = db.execute(
        select(AuditLog).where(
            AuditLog.action == "area.deleted", AuditLog.entity_id == str(area["id"])
        )
    ).scalar_one()
    assert deleted.before["name"] == "منطقة مؤقتة" and deleted.after is None


# --- towers -----------------------------------------------------------------------------------


def test_tower_code_uppercased_and_unique(client, h) -> None:
    area = _area(client, h)
    tower = _tower(client, h, area["id"], code=" alm01 ")
    assert tower["code"] == "ALM01" and tower["area"]["name"] == "العلم"
    for dup in ("ALM01", "alm01", "Alm01"):
        r = client.post(
            f"{BASE}/towers", json={"code": dup, "name": "x", "area_id": area["id"]}, headers=h
        )
        assert (r.status_code, r.json()["code"]) == (409, "code_taken"), dup


@pytest.mark.parametrize("code", ["ALM-01", "ALM 01", "A", "علم01", "ALM01_", "A" * 21])
def test_invalid_codes(client, h, code) -> None:
    area = _area(client, h)
    r = client.post(
        f"{BASE}/towers", json={"code": code, "name": "x", "area_id": area["id"]}, headers=h
    )
    assert r.json() == {"code": "invalid_code", "message": "الرمز أحرف إنجليزية كبيرة وأرقام فقط"}


def test_new_tower_needs_active_area_but_can_move(client, db, h) -> None:
    alam, samra = _area(client, h), _area(client, h, "سمرة")
    client.post(f"{BASE}/areas/{samra['id']}/deactivate", headers=h)
    r = client.post(
        f"{BASE}/towers",
        json={"code": "SMR01", "name": "سمرة 1", "area_id": samra["id"]},
        headers=h,
    )
    assert r.json()["code"] == "area_inactive"

    tower = _tower(client, h, alam["id"])
    r = client.patch(f"{BASE}/towers/{tower['id']}", json={"area_id": samra["id"]}, headers=h)
    assert r.status_code == 200 and r.json()["area"]["name"] == "سمرة"
    entry = db.execute(
        select(AuditLog).where(
            AuditLog.action == "tower.updated", AuditLog.entity_id == str(tower["id"])
        )
    ).scalar_one()
    assert (entry.before, entry.after) == ({"area": "العلم"}, {"area": "سمرة"})


def test_used_tower_cannot_be_deleted_fk_backstop(client, db, h) -> None:
    """A reference no registry check knows about: the ON DELETE RESTRICT FK still protects."""
    tower = _tower(client, h, _area(client, h)["id"])
    # A real table (Postgres forbids temp → permanent FKs). DDL is transactional, so the per-test
    # rollback in conftest removes it again.
    db.execute(
        text(
            "CREATE TABLE request_stub "
            "(tower_id bigint NOT NULL REFERENCES towers(id) ON DELETE RESTRICT)"
        )
    )
    db.execute(text("INSERT INTO request_stub VALUES (:t)"), {"t": tower["id"]})

    r = client.delete(f"{BASE}/towers/{tower['id']}", headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "item_in_use")
    assert db.get(Tower, tower["id"]) is not None
    assert "tower.deleted" not in _actions(db, "tower", tower["id"])


def test_used_tower_registry_locks_code_and_hides_delete(client, db, h) -> None:
    tower = _tower(client, h, _area(client, h)["id"])

    def used(_db, tower_id: int) -> int:
        return 1 if tower_id == tower["id"] else 0

    settings_service.register_usage_check("tower", used)
    try:
        listed = client.get(f"{BASE}/towers", headers=h).json()["items"]
        assert next(t for t in listed if t["id"] == tower["id"])["in_use"] is True
        r = client.patch(f"{BASE}/towers/{tower['id']}", json={"code": "ALM02"}, headers=h)
        assert (r.status_code, r.json()["code"]) == (409, "code_locked")
        r = client.patch(f"{BASE}/towers/{tower['id']}", json={"name": "العلم الأول"}, headers=h)
        assert r.status_code == 200 and r.json()["code"] == "ALM01"
        assert (
            client.delete(f"{BASE}/towers/{tower['id']}", headers=h).json()["code"] == "item_in_use"
        )
    finally:
        settings_service.unregister_usage_check("tower", used)


def test_unused_tower_deleted(client, db, h) -> None:
    tower = _tower(client, h, _area(client, h)["id"], code="TMP01")
    assert client.delete(f"{BASE}/towers/{tower['id']}", headers=h).status_code == 204
    assert db.get(Tower, tower["id"]) is None
    assert _actions(db, "tower", tower["id"]) == ["tower.created", "tower.deleted"]


def test_unknown_collection_and_id(client, h) -> None:
    assert client.post(f"{BASE}/nothing/1/deactivate", headers=h).status_code == 404
    assert client.delete(f"{BASE}/towers/999999999", headers=h).status_code == 404


# --- feature 008: a submitted request uses its area and tower (research R9) -----------------


def test_tower_and_area_used_by_a_request_cannot_be_deleted(client, db, h, make_user) -> None:
    from app.models import Area, Plan, Tower
    from tests.helpers.requests import request_factory

    area = _area(client, h, name="منطقة طلب")
    tower = _tower(client, h, area["id"], code="REQ01", name="برج طلب")
    plan = Plan(name="REQPLAN", trial_price=1, second_price=2)
    db.add(plan)
    db.flush()
    request_factory(
        db,
        make_user("marketer"),
        status="rejected",
        area=db.get(Area, area["id"]),
        tower=db.get(Tower, tower["id"]),
        plan=plan,
    )
    r = client.delete(f"{BASE}/towers/{tower['id']}", headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "item_in_use")
    listed = {t["id"]: t for t in client.get(f"{BASE}/towers", headers=h).json()["items"]}
    assert listed[tower["id"]]["in_use"] is True
