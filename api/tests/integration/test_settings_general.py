"""US4 — OTP validity in minutes (specs/004 contracts/api.md › General)."""

import pytest
from sqlalchemy import select

from app.models import AppSetting, AuditLog
from tests.conftest import auth_header, login

URL = "/api/admin/settings/general"


@pytest.fixture
def admin(make_user, db):
    a = make_user("admin")
    a.permissions = ["settings"]
    db.flush()
    return a


@pytest.fixture
def h(client, admin):
    return auth_header(login(client, admin.phone))


def test_default_is_60(client, h) -> None:
    assert client.get(URL, headers=h).json() == {"otp_validity_minutes": 60}


def test_update_stored_and_audited(client, db, admin, h) -> None:
    r = client.patch(URL, json={"otp_validity_minutes": 30}, headers=h)
    assert r.json() == {"otp_validity_minutes": 30}
    assert client.get(URL, headers=h).json() == {"otp_validity_minutes": 30}
    row = db.get(AppSetting, "otp_validity_minutes")
    assert row.value == 30 and row.updated_by == admin.id

    client.patch(URL, json={"otp_validity_minutes": 30}, headers=h)  # no-op
    [entry] = list(
        db.execute(select(AuditLog).where(AuditLog.action == "app_setting.updated")).scalars()
    )
    assert entry.entity_type == "app_setting" and entry.entity_id == "otp_validity_minutes"
    assert (entry.before, entry.after) == (
        {"otp_validity_minutes": 60},
        {"otp_validity_minutes": 30},
    )


@pytest.mark.parametrize("value", [5, 1440])
def test_bounds_allowed(client, h, value) -> None:
    assert client.patch(URL, json={"otp_validity_minutes": value}, headers=h).status_code == 200


@pytest.mark.parametrize("value", [4, 1441, 0, -1])
def test_out_of_range(client, h, value) -> None:
    r = client.patch(URL, json={"otp_validity_minutes": value}, headers=h)
    assert r.json() == {
        "code": "invalid_otp_minutes",
        "message": "المدة يجب أن تكون من 5 إلى 1,440 دقيقة",
    }


@pytest.mark.parametrize(
    "body",
    [{"otp_validity_minutes": 2.5}, {"otp_validity_minutes": "30"}, {"backup_path": "/x"}, {}],
)
def test_malformed(client, h, body) -> None:
    r = client.patch(URL, json=body, headers=h)
    assert (r.status_code, r.json()["code"]) == (422, "validation_error")


def test_permission(client, make_user, db) -> None:
    a = make_user("admin")
    a.permissions = ["review"]
    db.flush()
    for user in (a, make_user("marketer")):
        hh = auth_header(login(client, user.phone))
        assert client.get(URL, headers=hh).status_code == 403
        assert client.patch(URL, json={"otp_validity_minutes": 30}, headers=hh).status_code == 403
