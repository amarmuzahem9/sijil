"""«الاتصال بالإدارة» (specs/009 US2; FR-005a, FR-005b, FR-014; owner's Q1).

The administration's WhatsApp number lives in the general settings (`settings`). Signed-in users
read it from client-config. Opening the button is audited with the draft id only.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import AppSetting, AuditLog, Draft
from tests.conftest import auth_header, login

URL = "/api/admin/settings/general"


@pytest.fixture
def admin(make_user, db):
    a = make_user("admin")
    a.permissions = ["settings"]
    db.flush()
    return a


@pytest.fixture
def ah(client, admin):
    return auth_header(login(client, admin.phone))


def _marketer(client, make_user):
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


@pytest.fixture
def mh(client, make_user):
    return _marketer(client, make_user)


# --- the setting ---------------------------------------------------------------------------


def test_empty_by_default(client, ah) -> None:
    assert client.get(URL, headers=ah).json()["admin_whatsapp"] is None


def test_set_normalized_and_audited(client, db, admin, ah) -> None:
    r = client.patch(URL, json={"admin_whatsapp": "+964 770 111 2233"}, headers=ah)
    assert r.status_code == 200, r.json()
    assert r.json() == {"otp_validity_minutes": 60, "admin_whatsapp": "07701112233"}
    assert db.get(AppSetting, "admin_whatsapp").value == "07701112233"
    [entry] = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.action == "app_setting.updated", AuditLog.entity_id == "admin_whatsapp"
            )
        )
    )
    assert (entry.before, entry.after) == (
        {"admin_whatsapp": None},
        {"admin_whatsapp": "07701112233"},
    )


def test_each_key_changes_alone(client, ah) -> None:
    client.patch(URL, json={"admin_whatsapp": "07701112233"}, headers=ah)
    r = client.patch(URL, json={"otp_validity_minutes": 30}, headers=ah)
    assert r.json() == {"otp_validity_minutes": 30, "admin_whatsapp": "07701112233"}


@pytest.mark.parametrize("empty", ["", "   ", None])
def test_empty_clears(client, db, ah, empty) -> None:
    client.patch(URL, json={"admin_whatsapp": "07701112233"}, headers=ah)
    r = client.patch(URL, json={"admin_whatsapp": empty}, headers=ah)
    assert r.json()["admin_whatsapp"] is None
    assert db.get(AppSetting, "admin_whatsapp") is None


@pytest.mark.parametrize("bad", ["0770111", "12345678901", "abc"])
def test_invalid_number(client, ah, bad) -> None:
    r = client.patch(URL, json={"admin_whatsapp": bad}, headers=ah)
    assert (r.status_code, r.json()["code"]) == (422, "invalid_phone")


def test_needs_settings_permission(client, make_user, db) -> None:
    a = make_user("admin")
    a.permissions = ["review"]
    db.flush()
    hh = auth_header(login(client, a.phone))
    assert client.patch(URL, json={"admin_whatsapp": "07701112233"}, headers=hh).status_code == 403


# --- client-config ---------------------------------------------------------------------------


def test_client_config_gives_the_number_to_a_marketer(client, ah, mh) -> None:
    assert client.get("/api/client-config", headers=mh).json()["admin_whatsapp"] is None
    client.patch(URL, json={"admin_whatsapp": "07701112233"}, headers=ah)
    assert client.get("/api/client-config", headers=mh).json()["admin_whatsapp"] == "07701112233"


# --- contact-admin ---------------------------------------------------------------------------


def _draft(client, h) -> str:
    draft_id = str(uuid.uuid4())
    res = client.put(
        f"/api/drafts/{draft_id}", json={"changes": {"phone_input": "07801234567"}}, headers=h
    )
    assert res.status_code == 201, res.json()
    return draft_id


def test_contact_admin_is_audited_and_changes_nothing(client, db, mh) -> None:
    draft_id = _draft(client, mh)
    version = db.get(Draft, uuid.UUID(draft_id)).version

    res = client.post(f"/api/drafts/{draft_id}/contact-admin", headers=mh)

    assert res.status_code == 204
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)).version == version
    [entry] = list(
        db.scalars(select(AuditLog).where(AuditLog.action == "draft.contact_admin_opened"))
    )
    assert (entry.entity_type, entry.entity_id) == ("draft", draft_id)
    assert not entry.after  # draft id only: no phone, no numbers
    assert "07801234567" not in str(entry.before) + str(entry.after)


def test_contact_admin_on_another_marketers_draft_is_404(client, make_user, mh) -> None:
    draft_id = _draft(client, mh)
    other = _marketer(client, make_user)
    res = client.post(f"/api/drafts/{draft_id}/contact-admin", headers=other)
    assert res.status_code == 404
