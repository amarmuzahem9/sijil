"""«تراجع بعد الدفع» (docs/system.md v1.23 §9; specs/017 US4, FR-015, FR-016; research R6;
contracts/api.md › report row alerts, admin home). The paid figures never move; the report keeps
every alert; the admin home warns for undos of the last 30 days. Synthetic data only."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.schemas.admin_links import UnlinkIn
from app.services import link_service
from tests.helpers.requests import pay_month, request_factory
from tests.helpers.review import admin_with, headers_for

PAID_AT = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
UNDO_AT = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
MONTH = date(2026, 10, 1)


@pytest.fixture
def boss(make_user):
    return admin_with(make_user, "commissions", "link")


@pytest.fixture
def alice(make_user):
    return make_user("marketer")


def _paid_october(db, alice, boss, n=3):
    requests = [request_factory(db, alice, status="linked", linked_at=OCTOBER) for _ in range(n)]
    pay_month(db, alice, MONTH, boss, requests, at=PAID_AT)
    return requests


def _undo(db, request, admin, reason="not_linked_in_sas"):
    link_id = link_service._current_link_id(db, request)
    link_service.unlink(db, admin, request.id, UnlinkIn(reason=reason, link_id=link_id))


def _row(client, user, month="2026-10"):
    res = client.get(f"/api/admin/commissions?month={month}", headers=headers_for(client, user))
    assert res.status_code == 200, res.json()
    return res.json()["rows"][0]


def _home(client, user):
    res = client.get("/api/admin/home", headers=headers_for(client, user))
    assert res.status_code == 200, res.json()
    return res.json()


def test_undo_after_payment_keeps_figures_and_adds_an_alert(
    client, db, boss, alice, frozen_clock
) -> None:
    frozen_clock.set(UNDO_AT)
    first, *_ = _paid_october(db, alice, boss)
    _undo(db, first, boss)

    row = _row(client, boss)
    assert (row["count"], row["rate"], row["amount"]) == (3, 5000, 15000)
    assert row["payment"]["count_today"] == 2
    assert row["alerts"] == [
        {
            "number_label": first.number_label,
            "at": UNDO_AT.isoformat().replace("+00:00", "Z"),
            "reason": "not_linked_in_sas",
        }
    ]


def test_an_undo_before_payment_adds_no_alert(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(UNDO_AT)
    requests = [request_factory(db, alice, status="linked", linked_at=OCTOBER) for _ in range(3)]
    frozen_clock.set(PAID_AT - timedelta(days=1))
    _undo(db, requests[0], boss)
    frozen_clock.set(UNDO_AT)
    pay_month(db, alice, MONTH, boss, requests[1:], at=PAID_AT)
    row = _row(client, boss)
    assert row["alerts"] == []
    assert row["payment"]["count_today"] == 2


def test_relinked_after_payment_is_paid_before_not_counted(
    client, db, boss, alice, frozen_clock
) -> None:
    """FR-016, owner Q1."""
    frozen_clock.set(UNDO_AT)
    first, *_ = _paid_october(db, alice, boss)
    _undo(db, first, boss)
    link_service.link(db, boss, first.id)
    november = _row(client, boss, "2026-11")
    assert (november["count"], november["paid_before"]) == (0, 1)
    # Still one alert on the paid row: the re-link does not clear history.
    assert len(_row(client, boss)["alerts"]) == 1


def test_home_alert_by_role(client, db, boss, alice, make_user, frozen_clock) -> None:
    frozen_clock.set(UNDO_AT)
    first, *_ = _paid_october(db, alice, boss)
    _undo(db, first, boss)
    assert _home(client, make_user("super_admin"))["commission_alerts"] == 1
    assert _home(client, admin_with(make_user, "commissions"))["commission_alerts"] == 1
    assert _home(client, admin_with(make_user, "link"))["commission_alerts"] is None


def test_home_alert_window_is_30_days(client, db, boss, alice, make_user, frozen_clock) -> None:
    frozen_clock.set(UNDO_AT)
    first, *_ = _paid_october(db, alice, boss)
    _undo(db, first, boss)
    main = make_user("super_admin")

    frozen_clock.set(UNDO_AT + timedelta(days=30) - timedelta(minutes=1))
    assert _home(client, main)["commission_alerts"] == 1
    frozen_clock.set(UNDO_AT + timedelta(days=30) + timedelta(minutes=1))
    assert _home(client, main)["commission_alerts"] == 0
    # The report keeps the alert for good.
    assert len(_row(client, boss)["alerts"]) == 1


def test_no_alert_means_zero(client, db, boss, alice, make_user, frozen_clock) -> None:
    frozen_clock.set(UNDO_AT)
    _paid_october(db, alice, boss)
    assert _home(client, make_user("super_admin"))["commission_alerts"] == 0
