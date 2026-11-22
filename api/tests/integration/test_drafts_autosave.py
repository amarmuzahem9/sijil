"""US1 — autosave of drafts with `version` and `X-Client-Id` (specs/005 research.md R1, R3)."""

import uuid

import pytest

from tests.conftest import auth_header, login


def _h(response, client_id: str | None = None) -> dict[str, str]:
    headers = auth_header(response)
    headers["X-Client-Id"] = client_id or str(uuid.uuid4())
    return headers


@pytest.fixture
def marketer(client, make_user):
    user = make_user("marketer")
    return user, login(client, user.phone)


@pytest.fixture
def h(marketer):
    return _h(marketer[1])


def _create(client, h, changes=None, draft_id=None):
    draft_id = draft_id or str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": changes or {}}, headers=h)
    return draft_id, res


# --- create (PUT) ----------------------------------------------------------------------------


def test_put_creates_draft_with_version_1(client, h) -> None:
    draft_id, res = _create(client, h, {"subscriber_name": "  مشترك تجريبي  "})
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == draft_id
    assert body["version"] == 1
    assert body["status"] == "draft"
    assert body["subscriber_name"] == "مشترك تجريبي"
    assert body["images"] == {"front": None, "back": None}
    assert body["missing"][0] == {"field": "image_front", "code": "required"}


def test_repeated_put_is_idempotent(client, h) -> None:
    draft_id, _ = _create(client, h, {"address": "حي تجريبي"})
    again = client.put(
        f"/api/drafts/{draft_id}", json={"changes": {"address": "قيمة أخرى"}}, headers=h
    )
    assert again.status_code == 200
    assert again.json()["version"] == 1
    assert again.json()["address"] == "حي تجريبي"


def test_put_with_another_owners_id_is_404(client, h, make_user) -> None:
    draft_id, _ = _create(client, h)
    other = _h(login(client, make_user("marketer").phone))
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=other)
    assert res.status_code == 404
    assert res.json()["code"] == "draft_not_found"


@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_admins_cannot_create_drafts(client, make_user, role) -> None:
    h = _h(login(client, make_user(role).phone))
    _, res = _create(client, h)
    assert res.status_code == 403


def test_anonymous_gets_401(client) -> None:
    res = client.put(
        f"/api/drafts/{uuid.uuid4()}",
        json={"changes": {}},
        headers={"X-Client-Id": str(uuid.uuid4())},
    )
    assert res.status_code == 401


@pytest.mark.parametrize("value", [None, "", "not-a-uuid"])
def test_missing_or_malformed_client_id_is_422(client, marketer, value) -> None:
    headers = auth_header(marketer[1])
    if value is not None:
        headers["X-Client-Id"] = value
    res = client.put(f"/api/drafts/{uuid.uuid4()}", json={"changes": {}}, headers=headers)
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


# --- PATCH -----------------------------------------------------------------------------------


def test_patch_updates_only_given_keys_and_bumps_version(client, h) -> None:
    draft_id, created = _create(client, h, {"subscriber_name": "مشترك", "address": "حي"})
    before = created.json()
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"address": "  حي جديد ", "landmark": None}},
        headers=h,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["version"] == 2
    assert body["address"] == "حي جديد"
    assert body["subscriber_name"] == "مشترك"
    assert body["updated_at"] >= before["updated_at"]


def test_patch_null_clears_and_empty_becomes_null(client, h) -> None:
    draft_id, _ = _create(client, h, {"subscriber_name": "مشترك", "address": "حي"})
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"subscriber_name": None, "address": "   "}},
        headers=h,
    )
    assert res.json()["subscriber_name"] is None
    assert res.json()["address"] is None


def test_patch_normalizes_phone(client, h) -> None:
    draft_id, _ = _create(client, h)
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"phone_input": "+964 780 123 4567"}},
        headers=h,
    )
    assert res.json()["phone_input"] == "+964 780 123 4567"
    assert res.json()["phone_normalized"] == "07801234567"
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 2, "changes": {"phone_input": "0780"}},
        headers=h,
    )
    assert res.json()["phone_normalized"] is None


def test_over_length_is_422_too_long_with_field(client, h) -> None:
    draft_id, _ = _create(client, h)
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"landmark": "أ" * 201}},
        headers=h,
    )
    assert res.status_code == 422
    assert res.json() == {
        "code": "too_long",
        "message": "النص أطول من المسموح",
        "field": "landmark",
    }
    # Nothing was saved, the version is unchanged.
    assert client.get(f"/api/drafts/{draft_id}", headers=h).json()["version"] == 1


def test_unknown_or_price_keys_are_422(client, h) -> None:
    draft_id, _ = _create(client, h)
    for key in ("nickname", "trial_price", "tower_code"):
        res = client.patch(
            f"/api/drafts/{draft_id}", json={"version": 1, "changes": {key: 1}}, headers=h
        )
        assert res.status_code == 422, key


def test_patch_without_client_id_is_422(client, marketer, h) -> None:
    draft_id, _ = _create(client, h)
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"address": "حي"}},
        headers=auth_header(marketer[1]),
    )
    assert res.status_code == 422


def test_another_marketers_draft_is_404_everywhere(client, h, make_user) -> None:
    draft_id, _ = _create(client, h)
    other = _h(login(client, make_user("marketer").phone))
    assert client.get(f"/api/drafts/{draft_id}", headers=other).status_code == 404
    assert client.get(f"/api/drafts/{draft_id}/version", headers=other).status_code == 404
    res = client.patch(f"/api/drafts/{draft_id}", json={"version": 1, "changes": {}}, headers=other)
    assert res.status_code == 404
    assert client.get(f"/api/drafts/{uuid.uuid4()}", headers=other).status_code == 404


# --- conflicts (analysis U1) -----------------------------------------------------------------


def test_stale_version_from_another_client_same_session_is_409(client, marketer) -> None:
    """Two tabs share one session; only X-Client-Id differs."""
    tab_a = _h(marketer[1])
    tab_b = _h(marketer[1])
    draft_id, _ = _create(client, tab_a)
    assert (
        client.patch(
            f"/api/drafts/{draft_id}",
            json={"version": 1, "changes": {"address": "من التبويب ب"}},
            headers=tab_b,
        ).status_code
        == 200
    )
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"address": "من التبويب أ"}},
        headers=tab_a,
    )
    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "draft_conflict"
    assert body["message"] == "تغيّرت المسودة من جهاز آخر"
    assert body["version"] == 2
    assert body["same_client"] is False
    assert "updated_at" in body
    # Last save wins: B's value is kept.
    assert client.get(f"/api/drafts/{draft_id}", headers=tab_a).json()["address"] == "من التبويب ب"


def test_stale_version_from_another_device_is_409(client, make_user) -> None:
    user = make_user("marketer")
    phone_a = _h(login(client, user.phone))
    phone_b = _h(login(client, user.phone))
    draft_id, _ = _create(client, phone_a)
    client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"address": "ب"}}, headers=phone_b
    )
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"address": "أ"}}, headers=phone_a
    )
    assert res.status_code == 409
    assert res.json()["same_client"] is False


def test_stale_version_from_same_client_is_409_same_client(client, marketer) -> None:
    h = _h(marketer[1])
    draft_id, _ = _create(client, h)
    client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"address": "أ"}}, headers=h
    )
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"landmark": "ب"}}, headers=h
    )
    assert res.status_code == 409
    assert res.json()["same_client"] is True
    assert res.json()["version"] == 2


def test_keep_mine_with_current_version_wins(client, marketer) -> None:
    tab_a, tab_b = _h(marketer[1]), _h(marketer[1])
    draft_id, _ = _create(client, tab_a)
    client.patch(
        f"/api/drafts/{draft_id}", json={"version": 1, "changes": {"address": "ب"}}, headers=tab_b
    )
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": 2, "changes": {"address": "أ"}}, headers=tab_a
    )
    assert res.status_code == 200
    assert res.json()["version"] == 3
    poll = client.get(f"/api/drafts/{draft_id}/version", headers=tab_b).json()
    assert poll["version"] == 3
    assert poll["same_client"] is False


# --- version endpoint ------------------------------------------------------------------------


def test_version_endpoint(client, marketer) -> None:
    h = _h(marketer[1])
    draft_id, created = _create(client, h)
    res = client.get(f"/api/drafts/{draft_id}/version", headers=h)
    assert res.status_code == 200
    assert res.json() == {
        "version": 1,
        "updated_at": created.json()["updated_at"],
        "same_client": True,
    }
    other_tab = _h(marketer[1])
    assert (
        client.get(f"/api/drafts/{draft_id}/version", headers=other_tab).json()["same_client"]
        is False
    )
    # Reads do not require the header.
    plain = auth_header(marketer[1])
    assert client.get(f"/api/drafts/{draft_id}/version", headers=plain).status_code == 200
