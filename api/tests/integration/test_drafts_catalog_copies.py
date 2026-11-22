"""US7 — subscription choice: catalog copies on every save, notices on reopening
(specs/005 research.md R2, R4; data-model.md › drafts copies)."""

import uuid

import pytest

from app.services import settings_service
from tests.conftest import auth_header, login

BASE = "/api/admin/settings"


@pytest.fixture
def admin(client, make_user):
    return auth_header(login(client, make_user("super_admin").phone))


@pytest.fixture
def h(client, make_user):
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


@pytest.fixture
def catalog(client, admin):
    alam = client.post(f"{BASE}/areas", json={"name": "العلم"}, headers=admin).json()
    samra = client.post(f"{BASE}/areas", json={"name": "سمرة"}, headers=admin).json()
    alm01 = client.post(
        f"{BASE}/towers",
        json={"code": "ALM01", "name": "العلم 1", "area_id": alam["id"]},
        headers=admin,
    ).json()
    smr01 = client.post(
        f"{BASE}/towers",
        json={"code": "SMR01", "name": "سمرة 1", "area_id": samra["id"]},
        headers=admin,
    ).json()
    plus = client.post(
        f"{BASE}/plans",
        json={"name": "PLUS", "trial_price": 20000, "second_price": 35000},
        headers=admin,
    ).json()
    return {"alam": alam, "samra": samra, "alm01": alm01, "smr01": smr01, "plus": plus}


def _draft(client, h, changes=None):
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": changes or {}}, headers=h)
    assert res.status_code == 201, res.json()
    return draft_id, res.json()


def _patch(client, h, draft_id, version, changes):
    return client.patch(
        f"/api/drafts/{draft_id}", json={"version": version, "changes": changes}, headers=h
    )


def _choice(c):
    return {"area_id": c["alam"]["id"], "tower_id": c["alm01"]["id"], "plan_id": c["plus"]["id"]}


# --- copies ----------------------------------------------------------------------------------


def test_save_copies_names_and_prices(client, h, catalog):
    draft_id, _ = _draft(client, h)
    res = _patch(client, h, draft_id, 1, _choice(catalog))
    assert res.status_code == 200
    body = res.json()
    assert (body["area_name"], body["tower_code"], body["plan_name"]) == ("العلم", "ALM01", "PLUS")
    assert (body["trial_price"], body["second_price"]) == (20000, 35000)
    assert body["notices"] == []


def test_create_also_copies(client, h, catalog):
    _, body = _draft(client, h, _choice(catalog))
    assert body["tower_code"] == "ALM01" and body["trial_price"] == 20000


@pytest.mark.parametrize(
    "key", ["trial_price", "second_price", "area_name", "tower_code", "plan_name"]
)
def test_client_cannot_send_copies(client, h, catalog, key):
    draft_id, _ = _draft(client, h)
    res = _patch(client, h, draft_id, 1, {key: 1})
    assert res.status_code == 422


def test_unknown_id_is_invalid_choice(client, h, catalog):
    draft_id, _ = _draft(client, h)
    for key in ("area_id", "tower_id", "plan_id"):
        res = _patch(client, h, draft_id, 1, {key: 999_999_999})
        assert res.status_code == 422, key
        assert res.json()["code"] == "invalid_choice"


# --- clearing --------------------------------------------------------------------------------


def test_tower_of_another_area_is_cleared(client, h, catalog):
    draft_id, _ = _draft(client, h)
    res = _patch(
        client,
        h,
        draft_id,
        1,
        {"area_id": catalog["alam"]["id"], "tower_id": catalog["smr01"]["id"]},
    )
    body = res.json()
    assert body["area_id"] == catalog["alam"]["id"]
    assert body["tower_id"] is None and body["tower_code"] is None
    assert {"field": "tower_id", "code": "choice_unavailable", "old": None, "new": None} in body[
        "notices"
    ]


def test_changing_area_clears_tower(client, h, catalog):
    draft_id, _ = _draft(client, h, _choice(catalog))
    body = _patch(client, h, draft_id, 1, {"area_id": catalog["samra"]["id"]}).json()
    assert body["tower_id"] is None and body["tower_code"] is None
    assert body["area_name"] == "سمرة"
    # Changing area and tower together keeps the new tower.
    res = _patch(
        client,
        h,
        draft_id,
        2,
        {"area_id": catalog["alam"]["id"], "tower_id": catalog["alm01"]["id"]},
    )
    assert res.status_code == 200, res.json()
    assert res.json()["tower_code"] == "ALM01"


@pytest.mark.parametrize("what", ["tower", "plan", "area"])
def test_deactivated_choice_is_cleared_on_next_save(client, h, admin, catalog, what):
    draft_id, _ = _draft(client, h, _choice(catalog))
    path = {
        "tower": f"towers/{catalog['alm01']['id']}",
        "plan": f"plans/{catalog['plus']['id']}",
        "area": f"areas/{catalog['alam']['id']}",
    }[what]
    assert client.post(f"{BASE}/{path}/deactivate", headers=admin).status_code == 200

    # GET reports it without changing the row.
    got = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    fields = {n["field"] for n in got["notices"] if n["code"] == "choice_unavailable"}
    expected = {"tower": {"tower_id"}, "plan": {"plan_id"}, "area": {"area_id", "tower_id"}}[what]
    assert fields == expected
    assert got["version"] == 1

    # The next save (of anything) clears it.
    body = _patch(client, h, draft_id, 1, {"address": "حي"}).json()
    if what == "plan":
        assert body["plan_id"] is None and body["plan_name"] is None and body["trial_price"] is None
    else:
        assert body["tower_id"] is None and body["tower_code"] is None
    if what == "area":
        assert body["area_id"] is None and body["area_name"] is None
    assert {n["field"] for n in body["notices"]} == expected


# --- price change ----------------------------------------------------------------------------


def test_one_save_bumps_version_once(client, h, catalog):
    draft_id, _ = _draft(client, h)
    assert _patch(client, h, draft_id, 1, _choice(catalog)).json()["version"] == 2
    assert (
        _patch(client, h, draft_id, 2, {"area_id": catalog["samra"]["id"]}).json()["version"] == 3
    )


def test_price_change_is_reported_then_refreshed(client, h, admin, catalog):
    draft_id, _ = _draft(client, h, _choice(catalog))
    client.patch(
        f"{BASE}/plans/{catalog['plus']['id']}", json={"second_price": 40000}, headers=admin
    )

    got = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    assert got["notices"] == [
        {
            "field": "plan_id",
            "code": "price_changed",
            "old": {"trial_price": 20000, "second_price": 35000},
            "new": {"trial_price": 20000, "second_price": 40000},
        }
    ]
    assert got["second_price"] == 35000  # GET never writes
    assert got["version"] == 1

    body = _patch(client, h, draft_id, 1, {}).json()
    assert body["second_price"] == 40000
    assert body["notices"] == []
    assert client.get(f"/api/drafts/{draft_id}", headers=h).json()["notices"] == []


def test_renamed_area_refreshes_silently(client, h, admin, catalog):
    draft_id, _ = _draft(client, h, _choice(catalog))
    client.patch(
        f"{BASE}/areas/{catalog['alam']['id']}", json={"name": "العلم الجديد"}, headers=admin
    )
    assert client.get(f"/api/drafts/{draft_id}", headers=h).json()["notices"] == []
    assert _patch(client, h, draft_id, 1, {}).json()["area_name"] == "العلم الجديد"


# --- deleted settings items (SET NULL) -------------------------------------------------------


def test_deleting_unused_tower_sets_draft_tower_null(client, h, admin, catalog):
    draft_id, _ = _draft(client, h, _choice(catalog))
    # A draft is not a request: the tower is still "unused" and can be deleted.
    res = client.delete(f"{BASE}/towers/{catalog['alm01']['id']}", headers=admin)
    assert res.status_code == 204
    got = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    assert got["tower_id"] is None
    assert {"field": "tower_id", "code": "choice_unavailable", "old": None, "new": None} in got[
        "notices"
    ]
    body = _patch(client, h, draft_id, 1, {}).json()
    assert body["tower_code"] is None


def test_drafts_register_no_usage_check(db, catalog):
    assert settings_service.in_use(db, "tower", catalog["alm01"]["id"]) is False
    assert settings_service.in_use(db, "plan", catalog["plus"]["id"]) is False
