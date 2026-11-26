"""«العمولات» — the monthly report and its details (docs/system.md v1.23 §9, §10 item 13;
specs/017 US2, FR-008 to FR-010, research R4, R7, R9; contracts/api.md). Default tiers:
0 → 5,000; 30 → 7,000; 50 → 10,000. Synthetic data only."""

from datetime import UTC, date, datetime

import pytest

from app.models import RequestLink
from tests.helpers.requests import link_request, pay_month, request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
SEPTEMBER = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)

# The only keys a detail line may carry (research R9): no phone, username, identity number,
# card field or image link.
DETAIL_KEYS = {"id", "number_label", "full_name", "type", "tower_name", "tower_code", "linked_at"}


@pytest.fixture
def boss(make_user):
    return admin_with(make_user, "commissions", name="أدمن عمولات تجريبي")


@pytest.fixture
def alice(make_user):
    return make_user("marketer", name="أ مسوّق تجريبي")


@pytest.fixture
def bob(make_user):
    return make_user("marketer", name="ب مسوّق تجريبي")


def _linked(db, marketer, at, n=1, **over):
    return [request_factory(db, marketer, status="linked", linked_at=at, **over) for _ in range(n)]


def _undo(db, request, admin, at):
    request.status, request.linked_at, request.linked_by = "approved", None, None
    db.add(
        RequestLink(
            request_id=request.id, kind="unlinked", actor_id=admin.id, at=at, reason="by_mistake"
        )
    )
    db.flush()


def _get(client, user, url):
    res = client.get(url, headers=headers_for(client, user))
    assert res.status_code == 200, res.json()
    return res.json()


def _report(client, user, month):
    return _get(client, user, f"/api/admin/commissions?month={month}")


# --- months (FR-008, research R7) ----------------------------------------------------------------


def test_months_from_the_earliest_link_to_now(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, SEPTEMBER)
    body = _get(client, boss, "/api/admin/commissions/months")
    assert body == {"items": ["2026-11", "2026-10", "2026-09"], "current": "2026-11"}


def test_months_with_no_data_is_the_current_month(client, boss, frozen_clock) -> None:
    frozen_clock.set(NOW)
    body = _get(client, boss, "/api/admin/commissions/months")
    assert body == {"items": ["2026-11"], "current": "2026-11"}


# --- report rows (FR-009) ------------------------------------------------------------------------


def test_rows_figures_and_total(client, db, boss, alice, bob, make_user, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER, 30)
    _linked(db, alice, OCTOBER, 1, type="return", counts_commission=False)
    _linked(db, bob, OCTOBER, 2)
    request_factory(db, make_user("marketer"), status="approved")  # accepted, not linked: no row

    body = _report(client, boss, "2026-10")
    assert body["month"] == "2026-10"
    assert body["month_label"] == "تشرين الأول 2026"
    assert body["finished"] is True
    assert body["total_amount"] == 30 * 7000 + 2 * 5000
    assert [r["marketer_name"] for r in body["rows"]] == ["أ مسوّق تجريبي", "ب مسوّق تجريبي"]
    a, b = body["rows"]
    assert a == {
        "marketer_id": alice.id,
        "marketer_name": "أ مسوّق تجريبي",
        "count": 30,
        "without_commission": 1,
        "paid_before": 0,
        "tier_min_count": 30,
        "rate": 7000,
        "amount": 210000,
        "payable": True,
        "payment": None,
        "alerts": [],
    }
    assert (b["count"], b["rate"], b["amount"]) == (2, 5000, 10000)


def test_the_current_month_is_not_payable(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, NOW)
    body = _report(client, boss, "2026-11")
    assert body["finished"] is False
    assert body["rows"][0]["payable"] is False


def test_a_row_with_only_without_commission_links(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER, 2, type="return", counts_commission=False)
    (row,) = _report(client, boss, "2026-10")["rows"]
    assert (row["count"], row["without_commission"], row["amount"]) == (0, 2, 0)
    assert row["payable"] is False


def test_an_undone_link_leaves_its_month(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    first, _second = _linked(db, alice, OCTOBER, 2)
    _undo(db, first, boss, NOW)
    (row,) = _report(client, boss, "2026-10")["rows"]
    assert row["count"] == 1


def test_archived_and_stopped_marketers_keep_their_row(
    client, db, boss, alice, bob, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER)
    _linked(db, bob, OCTOBER)
    alice.is_active = False
    bob.is_active, bob.archived_at, bob.archived_by = False, NOW, boss.id
    db.flush()
    assert {r["marketer_id"] for r in _report(client, boss, "2026-10")["rows"]} == {
        alice.id,
        bob.id,
    }


def test_a_paid_row_keeps_its_figures(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    paid = _linked(db, alice, OCTOBER, 3)
    payment = pay_month(db, alice, date(2026, 10, 1), boss, paid, rate=4000, at=NOW)
    _undo(db, paid[0], boss, NOW)
    (row,) = _report(client, boss, "2026-10")["rows"]
    assert (row["count"], row["rate"], row["amount"]) == (3, 4000, 12000)
    assert row["payable"] is False
    assert row["payment"] == {
        "paid_by_name": "أدمن عمولات تجريبي",
        "paid_at": payment.paid_at.isoformat().replace("+00:00", "Z"),
        "count_today": 2,
    }
    assert _report(client, boss, "2026-10")["total_amount"] == 12000


def test_paid_before_is_shown_apart(client, db, boss, alice, frozen_clock) -> None:
    """Owner Q1: paid in September, undone and linked again in October → not counted."""
    frozen_clock.set(NOW)
    request = _linked(db, alice, SEPTEMBER)[0]
    pay_month(db, alice, date(2026, 9, 1), boss, [request])
    _undo(db, request, boss, OCTOBER)
    link_request(db, request, boss, at=OCTOBER)
    (row,) = _report(client, boss, "2026-10")["rows"]
    assert (row["count"], row["paid_before"], row["amount"]) == (0, 1, 0)


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "abc", "2026-12", "2027-01"])
def test_bad_or_future_month(client, boss, frozen_clock, month) -> None:
    frozen_clock.set(NOW)
    res = client.get(f"/api/admin/commissions?month={month}", headers=headers_for(client, boss))
    assert (res.status_code, res.json()["code"]) == (422, "validation_error")


# --- details (FR-010) ----------------------------------------------------------------------------


def _detail(client, user, month, marketer):
    return _get(client, user, f"/api/admin/commissions/{month}/marketers/{marketer.id}")


def test_detail_lists_and_allow_list(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    counted = _linked(db, alice, OCTOBER, 2)
    without = _linked(db, alice, OCTOBER, 1, type="return", counts_commission=False)
    earlier = _linked(db, alice, SEPTEMBER)[0]
    pay_month(db, alice, date(2026, 9, 1), boss, [earlier])
    _undo(db, earlier, boss, OCTOBER)
    link_request(db, earlier, boss, at=OCTOBER)

    body = _detail(client, boss, "2026-10", alice)
    assert set(body) == {"counted", "without_commission", "paid_before"}
    assert {line["id"] for line in body["counted"]} == {r.id for r in counted}
    assert [line["id"] for line in body["without_commission"]] == [without[0].id]
    (before,) = body["paid_before"]
    assert (before["id"], before["paid_month"]) == (earlier.id, "2026-09")
    for line in body["counted"] + body["without_commission"]:
        assert set(line) == DETAIL_KEYS
    assert set(before) == DETAIL_KEYS | {"paid_month"}
    line = body["counted"][0]
    assert line["number_label"].startswith("T3C-")
    assert line["type"] == "new"


def test_detail_of_a_paid_row_is_the_stored_list(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    paid = _linked(db, alice, OCTOBER, 2)
    pay_month(db, alice, date(2026, 10, 1), boss, paid)
    _undo(db, paid[0], boss, NOW)
    body = _detail(client, boss, "2026-10", alice)
    lines = {line["id"]: line for line in body["counted"]}
    assert set(lines) == {r.id for r in paid}
    assert lines[paid[0].id]["linked_at"] is None  # undone after the payment
    assert lines[paid[1].id]["linked_at"] is not None


def test_detail_without_a_row_is_404(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    res = client.get(
        f"/api/admin/commissions/2026-10/marketers/{alice.id}", headers=headers_for(client, boss)
    )
    assert (res.status_code, res.json()["code"]) == (404, "not_found")


# --- one rule everywhere (SC-002) ----------------------------------------------------------------


def test_report_equals_the_marketer_home_and_past_months(
    client, db, boss, alice, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER, 31)
    _linked(db, alice, OCTOBER, 2, type="return", counts_commission=False)
    _linked(db, alice, NOW, 12)
    _linked(db, alice, NOW, 1, type="return", counts_commission=False)

    home = _get(client, alice, "/api/marketer/dashboard")
    (now_row,) = _report(client, boss, "2026-11")["rows"]
    assert (home["linked_this_month"], home["linked_without_commission"]) == (
        now_row["count"],
        now_row["without_commission"] + now_row["paid_before"],
    )
    assert (home["tier_rate"], home["expected_amount"]) == (now_row["rate"], now_row["amount"])

    (past,) = _get(client, alice, "/api/marketer/commissions/months")["items"]
    (october_row,) = _report(client, boss, "2026-10")["rows"]
    assert (past["count"], past["rate"], past["amount"]) == (
        october_row["count"],
        october_row["rate"],
        october_row["amount"],
    )
    assert past["without_commission"] == october_row["without_commission"]
