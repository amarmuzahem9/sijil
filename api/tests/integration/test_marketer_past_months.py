"""«الأشهر السابقة» for the marketer (docs/system.md v1.23 §4.2; specs/017 FR-007, research R7,
R9; contracts/api.md › marketer months). Default tiers: 0 → 5,000; 30 → 7,000; 50 → 10,000."""

from datetime import UTC, date, datetime

import pytest

from app.services import settings_service
from tests.helpers.requests import pay_month, request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
SEPTEMBER = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
URL = "/api/marketer/commissions/months"


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def _linked(db, marketer, at, n=1, **over):
    return [request_factory(db, marketer, status="linked", linked_at=at, **over) for _ in range(n)]


def _months(client, user) -> list[dict]:
    res = client.get(URL, headers=headers_for(client, user))
    assert res.status_code == 200, res.json()
    return res.json()["items"]


def test_finished_months_newest_first_with_paid_and_unpaid(
    client, db, make_user, marketer, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    admin = make_user("super_admin")
    september = _linked(db, marketer, SEPTEMBER, 3)
    pay_month(db, marketer, date(2026, 9, 1), admin, september, rate=5000)
    _linked(db, marketer, OCTOBER, 2)
    _linked(db, marketer, OCTOBER, 1, type="return", counts_commission=False)
    _linked(db, marketer, NOW, 4)  # the current month is never listed

    # Tiers change after September was paid: September keeps its figures, October moves.
    settings_service.replace_tiers(db, admin, [(0, 6000)])

    months = _months(client, marketer)
    assert [m["month"] for m in months] == ["2026-10", "2026-09"]
    october, september_line = months
    assert october == {
        "month": "2026-10",
        "month_label": "تشرين الأول 2026",
        "count": 2,
        "without_commission": 1,
        "rate": 6000,
        "amount": 12000,
        "paid": False,
    }
    assert september_line["count"] == 3
    assert (september_line["rate"], september_line["amount"]) == (5000, 15000)
    assert september_line["paid"] is True


def test_no_payer_no_alert_in_the_body(client, db, make_user, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    admin = make_user("super_admin")
    pay_month(db, marketer, date(2026, 9, 1), admin, _linked(db, marketer, SEPTEMBER))
    (line,) = _months(client, marketer)
    assert set(line) == {
        "month",
        "month_label",
        "count",
        "without_commission",
        "rate",
        "amount",
        "paid",
    }


def test_a_month_with_only_undone_links_is_not_listed(client, db, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    request_factory(db, marketer, status="approved")  # accepted, never linked
    assert _months(client, marketer) == []


def test_only_the_callers_months(client, db, make_user, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, make_user("marketer"), OCTOBER, 2)
    assert _months(client, marketer) == []


def test_admins_are_refused(client, make_user) -> None:
    for admin in (make_user("super_admin"), admin_with(make_user, "commissions")):
        res = client.get(URL, headers=headers_for(client, admin))
        assert res.status_code == 403
