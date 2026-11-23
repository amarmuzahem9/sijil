"""The marketer's own requests (specs/008 T020, FR-019, contracts GET /api/requests)."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.submit import complete_draft, make_catalog, marketer_headers, submit


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    get_otp_sender().outbox.clear()
    return tmp_path


@pytest.fixture
def catalog(client, make_user):
    return make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))


@pytest.fixture
def me(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, me):
    return marketer_headers(client, me)


def test_list_is_own_newest_first_and_filters(client, db, h, make_user, catalog) -> None:
    approved = submit(client, h, complete_draft(client, h, catalog)).json()
    pending = submit(
        client, h, complete_draft(client, h, catalog, phone="07801234568", read_card=False)
    ).json()
    request_factory(db, make_user("marketer"))  # someone else's

    items = client.get("/api/requests", headers=h).json()["items"]
    assert [i["id"] for i in items] == [pending["id"], approved["id"]]
    assert set(items[0]) == {"id", "number_label", "full_name", "status", "type", "submitted_at"}
    assert items[1]["number_label"] == approved["number_label"]

    only = client.get("/api/requests", params={"status": "pending_review"}, headers=h)
    assert [i["id"] for i in only.json()["items"]] == [pending["id"]]
    both = client.get(
        "/api/requests", params=[("status", "approved"), ("status", "pending_review")], headers=h
    )
    assert len(both.json()["items"]) == 2


def test_get_own_request_and_hide_the_rest(client, db, h, make_user, catalog) -> None:
    created = submit(client, h, complete_draft(client, h, catalog)).json()
    res = client.get(f"/api/requests/{created['id']}", headers=h)
    assert res.status_code == 200 and res.json() == created
    for secret in (NID, FAMILY, "card_readings", "raw"):
        assert secret not in res.text

    other = request_factory(db, make_user("marketer"))
    res = client.get(f"/api/requests/{other.id}", headers=h)
    assert (res.status_code, res.json()["code"]) == (404, "request_not_found")
    assert client.get("/api/requests/999999", headers=h).status_code == 404


def test_username_hidden_until_approved(client, db, h, me) -> None:
    pending = request_factory(db, me, status="pending_review")
    body = client.get(f"/api/requests/{pending.id}", headers=h).json()
    assert body["username"] is None and body["result"] == "pending_review"


def test_admins_cannot_use_the_marketer_routes(client, make_user) -> None:
    admin = auth_header(login(client, make_user("super_admin").phone))
    assert client.get("/api/requests", headers=admin).status_code == 403
