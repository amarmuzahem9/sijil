"""The tier block on the marketer home (docs/system.md v1.23 §4.2, §9; specs/017 US1, FR-003,
FR-006, FR-016; contracts/api.md › dashboard). Default tiers: 0 → 5,000; 30 → 7,000; 50 → 10,000."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import RequestLink
from app.services import settings_service
from tests.helpers.requests import link_request, pay_month, request_factory
from tests.helpers.review import headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def _link_many(db, marketer, n: int, **over) -> list:
    return [
        request_factory(db, marketer, status="linked", linked_at=NOW - timedelta(minutes=i), **over)
        for i in range(n)
    ]


def _dashboard(client, marketer) -> dict:
    res = client.get("/api/marketer/dashboard", headers=headers_for(client, marketer))
    assert res.status_code == 200, res.json()
    return res.json()


@pytest.mark.parametrize(
    ("count", "rate", "amount", "next_tier"),
    [
        (0, 5000, 0, {"remaining": 30, "rate": 7000}),
        (27, 5000, 135000, {"remaining": 3, "rate": 7000}),
        (30, 7000, 210000, {"remaining": 20, "rate": 10000}),
        (50, 10000, 500000, None),
    ],
)
def test_tier_amount_and_next(
    client, db, marketer, frozen_clock, count, rate, amount, next_tier
) -> None:
    frozen_clock.set(NOW)
    _link_many(db, marketer, count)
    body = _dashboard(client, marketer)
    assert body["linked_this_month"] == count
    assert body["tier_rate"] == rate
    assert body["expected_amount"] == amount
    assert body["next_tier"] == next_tier


def test_without_commission_and_paid_before_do_not_change_the_amount(
    client, db, make_user, marketer, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    admin = make_user("super_admin")
    _link_many(db, marketer, 5)
    _link_many(db, marketer, 2, type="return", counts_commission=False)
    # Paid in October, undone and linked again this month (owner Q1).
    paid = request_factory(db, marketer, status="linked", linked_at=OCTOBER)
    pay_month(db, marketer, date(2026, 10, 1), admin, [paid])
    paid.status, paid.linked_at, paid.linked_by = "approved", None, None
    db.add(
        RequestLink(
            request_id=paid.id, kind="unlinked", actor_id=admin.id, at=NOW, reason="by_mistake"
        )
    )
    db.flush()
    link_request(db, paid, admin, at=NOW)

    body = _dashboard(client, marketer)
    assert body["linked_this_month"] == 5
    assert body["linked_without_commission"] == 3
    assert body["expected_amount"] == 5 * 5000


def test_a_tier_change_applies_at_once(client, db, make_user, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _link_many(db, marketer, 10)
    assert _dashboard(client, marketer)["expected_amount"] == 50000
    settings_service.replace_tiers(db, make_user("super_admin"), [(0, 6000), (10, 8000)])
    body = _dashboard(client, marketer)
    assert (body["tier_rate"], body["expected_amount"], body["next_tier"]) == (8000, 80000, None)
