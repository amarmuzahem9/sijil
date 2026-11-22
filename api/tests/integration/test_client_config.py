"""US6 — map configuration for the browser and the house location on drafts
(specs/005 research.md R10, data-model.md › drafts.location_*)."""

import uuid

import pytest

from app.config import get_settings
from tests.conftest import auth_header, login


@pytest.fixture
def h(client, make_user):
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


# --- /api/client-config ----------------------------------------------------------------------


def test_no_key_means_no_map(client, h, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "google_maps_api_key", "")
    res = client.get("/api/client-config", headers=h)
    assert res.status_code == 200
    assert res.json() == {"maps": None}


def test_with_key_returns_map_config(client, h, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "google_maps_api_key", "test-key-not-real")
    monkeypatch.setattr(settings, "google_maps_map_id", "test-map-id")
    monkeypatch.setattr(settings, "map_default_center", "33.5,44.25")
    res = client.get("/api/client-config", headers=h)
    assert res.json() == {
        "maps": {
            "api_key": "test-key-not-real",
            "map_id": "test-map-id",
            "default_center": {"lat": 33.5, "lng": 44.25},
        }
    }


@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_any_signed_in_role(client, make_user, role) -> None:
    res = client.get(
        "/api/client-config", headers=auth_header(login(client, make_user(role).phone))
    )
    assert res.status_code == 200


def test_anonymous_gets_401(client) -> None:
    assert client.get("/api/client-config").status_code == 401


# --- drafts.location_* -----------------------------------------------------------------------


def _draft(client, h) -> str:
    draft_id = str(uuid.uuid4())
    assert client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=h).status_code == 201
    return draft_id


def test_patch_location_stores_all_fields(client, h) -> None:
    draft_id = _draft(client, h)
    loc = {"lat": 33.312805, "lng": 44.361488, "source": "gps", "accuracy_m": 12}
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"location": loc}}, headers=h
    )
    assert res.status_code == 200
    assert res.json()["location"] == loc
    assert "location" not in [m["field"] for m in res.json()["missing"]]

    moved = {"lat": 33.3131, "lng": 44.3619, "source": "map"}
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 2, "changes": {"location": moved}}, headers=h
    )
    assert res.json()["location"] == {**moved, "accuracy_m": None}


@pytest.mark.parametrize(
    "loc",
    [
        {"lat": 91, "lng": 44, "source": "gps"},
        {"lat": 33, "lng": -181, "source": "gps"},
        {"lat": 33, "lng": 44, "source": "satellite"},
        {"lat": 33, "lng": 44, "source": "gps", "accuracy_m": -1},
        {"lat": 33, "source": "gps"},
    ],
)
def test_invalid_location_is_422(client, h, loc) -> None:
    draft_id = _draft(client, h)
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"location": loc}}, headers=h
    )
    assert res.status_code == 422


def test_null_clears_both_coordinates(client, h) -> None:
    draft_id = _draft(client, h)
    loc = {"lat": 33.3, "lng": 44.4, "source": "map"}
    client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"location": loc}}, headers=h
    )
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 2, "changes": {"location": None}}, headers=h
    )
    assert res.json()["location"] is None
    assert {"field": "location", "code": "required"} in res.json()["missing"]
