"""«تم الدفع» and the month lock (docs/system.md v1.23 §9; specs/017 US3, FR-005, FR-011 to FR-013,
FR-017, FR-018; research R5, R10; contracts/api.md › pay). Default tiers: 0 → 5,000; 30 → 7,000;
50 → 10,000. Synthetic data only."""

import logging
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, CommissionPayment, CommissionPaymentRequest
from app.services import settings_service
from tests.helpers.requests import pay_month, request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
PAY = "/api/admin/commissions/{month}/marketers/{marketer}/pay"


@pytest.fixture
def boss(make_user):
    return admin_with(make_user, "commissions", name="أدمن عمولات تجريبي")


@pytest.fixture
def alice(make_user):
    return make_user("marketer", name="مسوّق دفع تجريبي")


def _linked(db, marketer, at, n=1, **over):
    return [request_factory(db, marketer, status="linked", linked_at=at, **over) for _ in range(n)]


def _pay(client, user, marketer, body, month="2026-10"):
    return client.post(
        PAY.format(month=month, marketer=marketer.id), json=body, headers=headers_for(client, user)
    )


def _counts(db):
    return (
        db.scalar(select(func.count()).select_from(CommissionPayment)),
        db.scalar(select(func.count()).select_from(CommissionPaymentRequest)),
        db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "commission.paid")
        ),
    )


def test_pay_stores_the_figures_the_requests_and_one_audit_entry(
    client, db, boss, alice, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    requests = _linked(db, alice, OCTOBER, 30)
    _linked(db, alice, OCTOBER, 1, type="return", counts_commission=False)

    res = _pay(client, boss, alice, {"count": 30, "amount": 210000})
    assert res.status_code == 200, res.json()
    row = res.json()
    assert (row["count"], row["rate"], row["amount"], row["payable"]) == (30, 7000, 210000, False)
    assert row["payment"]["paid_by_name"] == "أدمن عمولات تجريبي"

    payment = db.scalar(select(CommissionPayment).where(CommissionPayment.marketer_id == alice.id))
    assert (
        payment.month,
        payment.count,
        payment.tier_min_count,
        payment.rate,
        payment.amount,
        payment.paid_by,
        payment.paid_at,
    ) == (date(2026, 10, 1), 30, 30, 7000, 210000, boss.id, NOW)
    stored = set(
        db.scalars(
            select(CommissionPaymentRequest.request_id).where(
                CommissionPaymentRequest.payment_id == payment.id
            )
        )
    )
    assert stored == {r.id for r in requests}

    (entry,) = db.scalars(select(AuditLog).where(AuditLog.action == "commission.paid")).all()
    assert (entry.actor_id, entry.entity_type, entry.entity_id) == (
        boss.id,
        "commission_payment",
        f"{alice.id}:2026-10",
    )
    assert entry.before is None
    assert entry.after == {
        "marketer_id": alice.id,
        "month": "2026-10",
        "count": 30,
        "tier_min_count": 30,
        "rate": 7000,
        "amount": 210000,
    }
    text = str(entry.after)
    for r in requests[:3]:
        assert str(r.number) not in text and r.full_name not in text


@pytest.mark.parametrize(
    ("month", "body", "status", "code"),
    [
        ("2026-11", {"count": 1, "amount": 5000}, 409, "month_not_finished"),
        ("2026-12", {"count": 1, "amount": 5000}, 422, "validation_error"),
        ("2026-10", {"count": 2, "amount": 10000}, 409, "commission_changed"),
        ("2026-10", {"count": 1, "amount": 7000}, 409, "commission_changed"),
        ("2026-10", {"count": -1, "amount": 5000}, 422, "validation_error"),
    ],
)
def test_refusals_write_nothing(
    client, db, boss, alice, frozen_clock, month, body, status, code
) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER)
    _linked(db, alice, NOW)
    res = _pay(client, boss, alice, body, month=month)
    assert (res.status_code, res.json()["code"]) == (status, code)
    assert _counts(db) == (0, 0, 0)


def test_nothing_to_pay(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER, 2, type="return", counts_commission=False)
    res = _pay(client, boss, alice, {"count": 0, "amount": 0})
    assert (res.status_code, res.json()["code"]) == (409, "nothing_to_pay")
    assert _counts(db) == (0, 0, 0)


def test_second_pay_is_already_paid(client, db, boss, alice, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER, 2)
    assert _pay(client, boss, alice, {"count": 2, "amount": 10000}).status_code == 200
    res = _pay(client, boss, alice, {"count": 2, "amount": 10000})
    assert (res.status_code, res.json()["code"]) == (409, "already_paid")
    assert _counts(db) == (1, 2, 1)


def test_unknown_marketer_and_admin_target(client, db, boss, make_user, frozen_clock) -> None:
    frozen_clock.set(NOW)
    for target_id in (999_999_999, make_user("super_admin").id):
        res = client.post(
            PAY.format(month="2026-10", marketer=target_id),
            json={"count": 1, "amount": 5000},
            headers=headers_for(client, boss),
        )
        assert (res.status_code, res.json()["code"]) == (404, "not_found")


@pytest.mark.parametrize("permission", ["review", "link", "settings", "marketers", "reports"])
def test_other_permissions_refused(client, db, alice, make_user, frozen_clock, permission) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER)
    res = _pay(client, admin_with(make_user, permission), alice, {"count": 1, "amount": 5000})
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")
    res = _pay(client, alice, alice, {"count": 1, "amount": 5000})
    assert res.status_code == 403
    assert _counts(db) == (0, 0, 0)


def test_the_main_admin_may_pay(client, db, alice, make_user, frozen_clock) -> None:
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER)
    assert (
        _pay(client, make_user("super_admin"), alice, {"count": 1, "amount": 5000}).status_code
        == 200
    )


def test_tier_change_after_pay_moves_only_unpaid_months(
    client, db, boss, alice, make_user, frozen_clock
) -> None:
    """FR-005: the paid month keeps its rate and amount; an unpaid one follows the new tiers."""
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER, 3)
    _linked(db, alice, datetime(2026, 9, 10, 9, 0, tzinfo=UTC), 2)
    assert _pay(client, boss, alice, {"count": 3, "amount": 15000}).status_code == 200
    settings_service.replace_tiers(db, make_user("super_admin"), [(0, 9000)])

    def row(month):
        res = client.get(f"/api/admin/commissions?month={month}", headers=headers_for(client, boss))
        return res.json()["rows"][0]

    assert (row("2026-10")["rate"], row("2026-10")["amount"]) == (5000, 15000)
    assert (row("2026-09")["rate"], row("2026-09")["amount"]) == (9000, 18000)


def test_the_log_holds_no_names_or_numbers(client, db, boss, alice, frozen_clock, caplog) -> None:
    """Principle II (T053): marketer id, month and amount only."""
    frozen_clock.set(NOW)
    (request,) = _linked(db, alice, OCTOBER)
    with caplog.at_level(logging.INFO, logger="sijil.commissions"):
        assert _pay(client, boss, alice, {"count": 1, "amount": 5000}).status_code == 200
    text = caplog.text
    assert f"marketer={alice.id}" in text and "month=2026-10" in text and "amount=5000" in text
    for value in (alice.name, alice.phone, request.full_name, request.phone, str(request.number)):
        assert value not in text


def test_the_helper_matches_the_service(client, db, boss, alice, make_user, frozen_clock) -> None:
    """T041: `pay_month` writes the same rows as `commission_service.pay`."""
    frozen_clock.set(NOW)
    other = make_user("marketer")
    by_service = _linked(db, alice, OCTOBER, 2)
    by_helper = _linked(db, other, OCTOBER, 2)
    assert _pay(client, boss, alice, {"count": 2, "amount": 10000}).status_code == 200
    pay_month(db, other, date(2026, 10, 1), boss, by_helper, at=NOW)

    def shape(marketer, requests):
        p = db.scalar(select(CommissionPayment).where(CommissionPayment.marketer_id == marketer.id))
        ids = set(
            db.scalars(
                select(CommissionPaymentRequest.request_id).where(
                    CommissionPaymentRequest.payment_id == p.id
                )
            )
        )
        return (
            p.month,
            p.count,
            p.tier_min_count,
            p.rate,
            p.amount,
            ids == {r.id for r in requests},
        )

    assert shape(alice, by_service) == shape(other, by_helper)


def test_the_audit_page_names_the_marketer(
    client, db, boss, alice, make_user, frozen_clock
) -> None:
    """research R10: the server labels the entry «عمولة {marketer} — {month}»."""
    frozen_clock.set(NOW)
    _linked(db, alice, OCTOBER)
    assert _pay(client, boss, alice, {"count": 1, "amount": 5000}).status_code == 200
    res = client.get("/api/admin/audit", headers=headers_for(client, make_user("super_admin")))
    entry = next(e for e in res.json()["items"] if e["action"] == "commission.paid")
    assert entry["target_label"] == f"عمولة {alice.name} — 2026-10"
