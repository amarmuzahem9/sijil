"""`link_message` on the marketer's request (specs/012 US1, FR-001, FR-005, FR-009;
contracts/api.md). Synthetic data only."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for, pending_request
from tests.helpers.submit import complete_draft, make_catalog, marketer_headers, submit


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    get_otp_sender().outbox.clear()
    return tmp_path


@pytest.fixture
def marketer(make_user):
    return make_user("marketer", name="مسوّق الربط")


def _get(client, h, request_id):
    res = client.get(f"/api/requests/{request_id}", headers=h)
    assert res.status_code == 200, res.json()
    return res.json()


def test_auto_accepted_submission_carries_the_message(client, make_user, marketer) -> None:
    catalog = make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))
    h = marketer_headers(client, marketer)
    res = submit(client, h, complete_draft(client, h, catalog))
    assert res.status_code == 201, res.json()
    body = res.json()
    assert body["status"] == "approved"
    lines = body["link_message"].splitlines()
    assert lines[0] == f"طلب ربط جديد | رقم الطلب: #{body['number_label']}"
    assert "البرج: برج 3 (ALM03)" in lines
    assert "الهاتف: 07801234567" in lines
    assert "الموقع: https://maps.google.com/?q=34.7,43.68" in lines
    assert lines[-1] == "المسوّق: مسوّق الربط"
    assert _get(client, h, body["id"])["link_message"] == body["link_message"]


def test_accepted_by_an_admin_has_it_pending_has_not(client, db, make_user, marketer) -> None:
    request = pending_request(db, marketer, [("numbers_edited", None, {})])
    h = marketer_headers(client, marketer)
    assert _get(client, h, request.id)["link_message"] is None

    admin = admin_with(make_user, "review")
    res = client.post(
        f"/api/admin/requests/{request.id}/accept", json={}, headers=headers_for(client, admin)
    )
    assert res.status_code == 200, res.json()
    text = _get(client, h, request.id)["link_message"]
    assert text.startswith(f"طلب ربط جديد | رقم الطلب: #{request.number_label}")
    assert request.national_id not in text
    assert request.family_number not in text


def test_rejected_and_deleted_have_no_message(client, db, make_user, marketer) -> None:
    h = marketer_headers(client, marketer)
    rejected = request_factory(db, marketer, status="rejected")
    assert _get(client, h, rejected.id)["link_message"] is None

    deleted = request_factory(db, marketer, status="pending_review")
    mark_deleted(db, deleted, admin_with(make_user, "review", "delete"))
    assert _get(client, h, deleted.id)["link_message"] is None


def test_linked_has_the_message(client, db, marketer) -> None:
    request = request_factory(db, marketer, status="linked")
    assert _get(client, marketer_headers(client, marketer), request.id)["link_message"]


def test_another_marketer_gets_not_found(client, db, make_user, marketer) -> None:
    request = request_factory(db, marketer)
    other = marketer_headers(client, make_user("marketer"))
    res = client.get(f"/api/requests/{request.id}", headers=other)
    assert res.status_code == 404
    assert "link_message" not in res.text
