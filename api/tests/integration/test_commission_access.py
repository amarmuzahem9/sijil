"""Who may read «العمولات» (docs/system.md v1.23 §3.3, §10 item 13; specs/017 FR-008, FR-013,
SC-006; constitution Principle IX). Main admin and `commissions` only; nobody edits a payment."""

import pytest

from tests.helpers.review import admin_with, headers_for

ROUTES = (
    "/api/admin/commissions/months",
    "/api/admin/commissions?month=2026-10",
    "/api/admin/commissions/2026-10/marketers/1",
)
OTHER_PERMISSIONS = ("review", "link", "settings", "marketers", "reports", "delete")


@pytest.mark.parametrize("url", ROUTES)
def test_without_a_session(client, url) -> None:
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("url", ROUTES)
def test_marketer_refused(client, make_user, url) -> None:
    res = client.get(url, headers=headers_for(client, make_user("marketer")))
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize("permission", OTHER_PERMISSIONS)
@pytest.mark.parametrize("url", ROUTES)
def test_other_permissions_refused(client, make_user, permission, url) -> None:
    res = client.get(url, headers=headers_for(client, admin_with(make_user, permission)))
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize("url", ROUTES[:2])
def test_main_admin_and_commissions_allowed(client, make_user, url) -> None:
    for user in (make_user("super_admin"), admin_with(make_user, "commissions")):
        assert client.get(url, headers=headers_for(client, user)).status_code == 200


@pytest.mark.parametrize("method", ["DELETE", "PATCH", "PUT"])
def test_no_route_edits_or_removes_a_payment(client, make_user, method) -> None:
    """FR-013: «تم الدفع» has no undo."""
    headers = headers_for(client, make_user("super_admin"))
    url = "/api/admin/commissions/2026-10/marketers/1/pay"
    assert client.request(method, url, headers=headers).status_code in (404, 405)
