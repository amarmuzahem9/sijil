"""FR-014 — /api/catalog for the new-request form (specs/004 research R3)."""

import pytest

from tests.conftest import auth_header, login

BASE = "/api/admin/settings"


@pytest.fixture
def h(client, make_user):
    return auth_header(login(client, make_user("super_admin").phone))


def _seed(client, h):
    alam = client.post(f"{BASE}/areas", json={"name": "العلم"}, headers=h).json()
    samra = client.post(f"{BASE}/areas", json={"name": "سمرة"}, headers=h).json()
    alm01 = client.post(
        f"{BASE}/towers",
        json={"code": "ALM01", "name": "العلم 1", "area_id": alam["id"]},
        headers=h,
    ).json()
    alm02 = client.post(
        f"{BASE}/towers",
        json={"code": "ALM02", "name": "العلم 2", "area_id": alam["id"]},
        headers=h,
    ).json()
    smr01 = client.post(
        f"{BASE}/towers",
        json={"code": "SMR01", "name": "سمرة 1", "area_id": samra["id"]},
        headers=h,
    ).json()
    plus = client.post(
        f"{BASE}/plans",
        json={"name": "PLUS", "trial_price": 20000, "second_price": 35000},
        headers=h,
    ).json()
    old = client.post(
        f"{BASE}/plans", json={"name": "OLD", "trial_price": 1, "second_price": 1}, headers=h
    ).json()
    client.post(f"{BASE}/towers/{alm02['id']}/deactivate", headers=h)
    client.post(f"{BASE}/areas/{samra['id']}/deactivate", headers=h)  # SMR01 stays active itself
    client.post(f"{BASE}/plans/{old['id']}/deactivate", headers=h)
    return alam, alm01, smr01, plus


@pytest.mark.parametrize("role", ["marketer", "admin", "super_admin"])
def test_only_active_items_for_any_signed_in_user(client, make_user, h, role) -> None:
    alam, alm01, smr01, plus = _seed(client, h)
    hh = auth_header(login(client, make_user(role).phone))
    r = client.get("/api/catalog", headers=hh)
    assert r.status_code == 200
    body = r.json()
    assert body["areas"] == [{"id": alam["id"], "name": "العلم"}]
    assert body["towers"] == [
        {"id": alm01["id"], "code": "ALM01", "name": "العلم 1", "area_id": alam["id"]}
    ]
    assert body["plans"] == [
        {"id": plus["id"], "name": "PLUS", "trial_price": 20000, "second_price": 35000}
    ]
    assert smr01["id"] not in {t["id"] for t in body["towers"]}


def test_anonymous_refused(client) -> None:
    assert client.get("/api/catalog").status_code == 401


def test_pending_password_change_refused(client, make_user) -> None:
    u = make_user("marketer", must_change_password=True)
    r = client.get("/api/catalog", headers=auth_header(login(client, u.phone)))
    assert r.json()["code"] == "password_change_required"
