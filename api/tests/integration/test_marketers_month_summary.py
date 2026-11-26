"""«المسوّقون»: this month's count and expected commission (docs/system.md v1.23 §10 item 5;
specs/017 US5, FR-019; contracts/api.md › month-summary). Same rule as the marketer home."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
URL = "/api/admin/marketers/month-summary"


@pytest.fixture
def manager(make_user):
    return admin_with(make_user, "marketers")


def test_count_and_amount_equal_the_marketer_home(
    client, db, manager, make_user, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    alice, bob = make_user("marketer"), make_user("marketer")
    for i in range(31):
        request_factory(db, alice, status="linked", linked_at=NOW - timedelta(minutes=i))
    request_factory(
        db, alice, status="linked", linked_at=NOW, type="return", counts_commission=False
    )
    request_factory(db, bob, status="linked", linked_at=NOW - timedelta(days=40))  # October

    res = client.get(URL, headers=headers_for(client, manager))
    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["month_label"] == "تشرين الثاني 2026"
    items = {i["marketer_id"]: i for i in body["items"]}
    assert items[alice.id] == {"marketer_id": alice.id, "count": 31, "amount": 31 * 7000}
    assert bob.id not in items  # nothing this month

    home = client.get("/api/marketer/dashboard", headers=headers_for(client, alice)).json()
    assert (items[alice.id]["count"], items[alice.id]["amount"]) == (
        home["linked_this_month"],
        home["expected_amount"],
    )


@pytest.mark.parametrize("permission", ["review", "link", "settings", "reports", "commissions"])
def test_refused_without_marketers(client, make_user, permission) -> None:
    res = client.get(URL, headers=headers_for(client, admin_with(make_user, permission)))
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")


def test_refused_for_a_marketer(client, make_user) -> None:
    res = client.get(URL, headers=headers_for(client, make_user("marketer")))
    assert res.status_code == 403


def test_the_main_admin_may_read(client, make_user) -> None:
    assert client.get(URL, headers=headers_for(client, make_user("super_admin"))).status_code == 200
