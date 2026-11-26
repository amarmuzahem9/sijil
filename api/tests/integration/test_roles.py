import pytest

from app.core.timeutil import baghdad_month_label
from tests.conftest import auth_header, login

# --- Admin side (US1) -------------------------------------------------------


@pytest.mark.parametrize("role", ["super_admin", "admin"])
def test_admin_roles_can_reach_admin_api(client, make_user, role) -> None:
    user = make_user(role)
    r = client.get("/api/admin/ping", headers=auth_header(login(client, user.phone)))
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_admin_api_requires_token(client) -> None:
    r = client.get("/api/admin/ping")
    assert r.status_code == 401 and r.json()["code"] == "not_authenticated"


# --- Marketer side (US2) ----------------------------------------------------


def test_marketer_refused_on_admin_api(client, make_user) -> None:
    user = make_user("marketer")
    r = client.get("/api/admin/ping", headers=auth_header(login(client, user.phone)))
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


def test_marketer_dashboard(client, make_user) -> None:
    user = make_user("marketer")
    r = client.get("/api/marketer/dashboard", headers=auth_header(login(client, user.phone)))
    assert r.status_code == 200
    # specs/013 and specs/017 contracts/api.md › dashboard: a marketer with no links yet, at the
    # first default tier (0 → 5,000; 30 → 7,000).
    assert r.json() == {
        "linked_this_month": 0,
        "linked_without_commission": 0,
        "month_label": baghdad_month_label(),
        "tier_rate": 5000,
        "expected_amount": 0,
        "next_tier": {"remaining": 30, "rate": 7000},
        "recent_links": [],
    }


@pytest.mark.parametrize("role", ["super_admin", "admin"])
def test_admins_refused_on_marketer_dashboard(client, make_user, role) -> None:
    user = make_user(role)
    r = client.get("/api/marketer/dashboard", headers=auth_header(login(client, user.phone)))
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
