"""US2 — categories and prices (specs/004 contracts/api.md)."""

import pytest
from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import auth_header, login

BASE = "/api/admin/settings/plans"


@pytest.fixture
def h(client, make_user, db):
    a = make_user("admin")
    a.permissions = ["settings"]
    db.flush()
    return auth_header(login(client, a.phone))


def _plan(client, h, name="PLUS", trial=20000, second=35000):
    r = client.post(
        BASE, json={"name": name, "trial_price": trial, "second_price": second}, headers=h
    )
    assert r.status_code == 201, r.json()
    return r.json()


def test_create_plus(client, h) -> None:
    plan = _plan(client, h)
    assert plan == {
        "id": plan["id"],
        "name": "PLUS",
        "trial_price": 20000,
        "second_price": 35000,
        "is_active": True,
        "in_use": False,
    }


@pytest.mark.parametrize("dup", ["PLUS", "plus", " Plus "])
def test_duplicate_name_ignoring_case(client, h, dup) -> None:
    _plan(client, h)
    r = client.post(BASE, json={"name": dup, "trial_price": 1, "second_price": 1}, headers=h)
    assert (r.status_code, r.json()["code"]) == (409, "name_taken")


def test_pl_us_is_a_different_name(client, h) -> None:
    _plan(client, h)
    assert _plan(client, h, name="PL US")["name"] == "PL US"


@pytest.mark.parametrize(
    ("trial", "status", "code"),
    [
        (-1, 422, "invalid_amount"),
        (10_000_001, 422, "invalid_amount"),
        (1.5, 422, "validation_error"),
        ("20,000", 422, "validation_error"),
        ("20000", 422, "validation_error"),
        (True, 422, "validation_error"),
    ],
)
def test_invalid_prices(client, h, trial, status, code) -> None:
    r = client.post(BASE, json={"name": "PLUS", "trial_price": trial, "second_price": 1}, headers=h)
    assert (r.status_code, r.json()["code"]) == (status, code)


def test_missing_price(client, h) -> None:
    r = client.post(BASE, json={"name": "PLUS", "trial_price": 1}, headers=h)
    assert r.status_code == 422


def test_zero_and_max_are_allowed(client, h) -> None:
    assert _plan(client, h, trial=0, second=10_000_000)["trial_price"] == 0


def test_price_change_audited_with_old_and_new(client, db, h) -> None:
    plan = _plan(client, h)
    r = client.patch(f"{BASE}/{plan['id']}", json={"second_price": 40000}, headers=h)
    assert r.json()["second_price"] == 40000
    client.patch(f"{BASE}/{plan['id']}", json={"second_price": 40000}, headers=h)  # no-op
    entries = list(
        db.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "plan",
                AuditLog.entity_id == str(plan["id"]),
                AuditLog.action == "plan.updated",
            )
        ).scalars()
    )
    assert len(entries) == 1
    assert (entries[0].before, entries[0].after) == (
        {"second_price": 35000},
        {"second_price": 40000},
    )


def test_state_and_delete(client, db, h) -> None:
    plan = _plan(client, h)
    assert client.post(f"{BASE}/{plan['id']}/deactivate", headers=h).json()["is_active"] is False
    assert client.post(f"{BASE}/{plan['id']}/reactivate", headers=h).json()["is_active"] is True
    assert client.delete(f"{BASE}/{plan['id']}", headers=h).status_code == 204
    actions = list(
        db.execute(
            select(AuditLog.action)
            .where(AuditLog.entity_type == "plan", AuditLog.entity_id == str(plan["id"]))
            .order_by(AuditLog.id)
        ).scalars()
    )
    assert actions == ["plan.created", "plan.deactivated", "plan.reactivated", "plan.deleted"]


def test_permission(client, make_user, db) -> None:
    a = make_user("admin")
    a.permissions = ["review", "marketers"]
    db.flush()
    for user in (a, make_user("marketer")):
        hh = auth_header(login(client, user.phone))
        assert client.get(BASE, headers=hh).status_code == 403
        r = client.post(BASE, json={"name": "X", "trial_price": 1, "second_price": 1}, headers=hh)
        assert r.status_code == 403
    main = auth_header(login(client, make_user("super_admin").phone))
    assert client.get(BASE, headers=main).status_code == 200
