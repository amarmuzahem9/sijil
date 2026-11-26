"""Commissions (docs/system.md v1.23 §9, specs/017 research R2–R7).

One count rule serves the marketer home, the past months, the report and the marketers page:
a marketer month is their requests linked now, not deleted, whose current link falls in the
Baghdad month. Each is `counted`, `without_commission` (a return accepted with «لا») or
`paid_before` (already in a payment, owner Q1). Legacy and SAS subscribers are not requests and
have no marketer, so they never enter it.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Date, case, exists, func, select
from sqlalchemy.orm import Session

from app.core import commission
from app.core.timeutil import BAGHDAD, baghdad_month_bounds, baghdad_month_label, utc_now
from app.models import CommissionPayment, CommissionPaymentRequest, Request, User
from app.services import settings_service


@dataclass(frozen=True)
class MonthSplit:
    counted: int
    without_commission: int
    # In a payment of an earlier month: never counted again (owner Q1).
    paid_before: int
    # In this month's own payment: its figures come from the payment (research R4).
    paid_here: int = 0


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """[start, end) in UTC of the Baghdad month whose first day is `month`."""
    return baghdad_month_bounds(datetime(month.year, month.month, 1, 12, tzinfo=BAGHDAD))


def _in_month(month: date):
    start, end = month_bounds(month)
    return (
        Request.status == "linked",
        Request.deleted_at.is_(None),
        Request.linked_at >= start,
        Request.linked_at < end,
    )


def current_month() -> date:
    """The first day of the current Baghdad month."""
    return utc_now().astimezone(BAGHDAD).date().replace(day=1)


def month_label(month: date) -> str:
    return baghdad_month_label(month_bounds(month)[0])


def _paid_in(month: date | None):
    """The request is in a payment (of `month` only, when given)."""
    query = exists().where(CommissionPaymentRequest.request_id == Request.id)
    if month is not None:
        query = query.where(
            CommissionPayment.id == CommissionPaymentRequest.payment_id,
            CommissionPayment.month == month,
        )
    return query


def _category(month: date):
    return case(
        (_paid_in(month), "paid_here"),
        (_paid_in(None), "paid_before"),
        (Request.counts_commission.is_(False), "without_commission"),
        else_="counted",
    )


def month_split(
    db: Session, month: date, marketer_ids: Iterable[int] | None = None
) -> dict[int, MonthSplit]:
    """Per marketer with at least one linked request in the month (research R2).

    A paid month's own requests are `paid_here`: its figures come from the payment (research R4).
    """
    category = _category(month).label("category")
    query = select(Request.marketer_id, category, func.count()).where(*_in_month(month))
    if marketer_ids is not None:
        query = query.where(Request.marketer_id.in_(list(marketer_ids)))
    rows = db.execute(query.group_by(Request.marketer_id, category)).all()
    numbers: dict[int, dict[str, int]] = {}
    for marketer_id, kind, n in rows:
        numbers.setdefault(marketer_id, {})[kind] = n
    return {
        marketer_id: MonthSplit(
            counted=n.get("counted", 0),
            without_commission=n.get("without_commission", 0),
            paid_before=n.get("paid_before", 0),
            paid_here=n.get("paid_here", 0),
        )
        for marketer_id, n in numbers.items()
    }


# --- the marketer (research R11, R7) -------------------------------------------------------------


@dataclass(frozen=True)
class MonthFigures:
    """What a marketer month shows: the count and money, and «بلا عمولة» (FR-003)."""

    month: date
    count: int
    without_commission: int
    tier_min_count: int
    rate: int
    amount: int
    next_tier: tuple[int, int] | None
    payment: CommissionPayment | None


def _figures(
    month: date, split: MonthSplit, payment: CommissionPayment | None, tiers
) -> MonthFigures:
    without = split.without_commission + split.paid_before
    if payment is not None:
        # Locked at «تم الدفع»: today's tiers and links never change it (FR-005).
        return MonthFigures(
            month,
            payment.count,
            without,
            payment.tier_min_count,
            payment.rate,
            payment.amount,
            None,
            payment,
        )
    tier_min, rate = commission.tier_for(split.counted, tiers)
    return MonthFigures(
        month,
        split.counted,
        without,
        tier_min,
        rate,
        commission.amount(split.counted, tiers),
        commission.next_tier(split.counted, tiers),
        None,
    )


_EMPTY = MonthSplit(0, 0, 0)


def marketer_current(db: Session, user: User) -> MonthFigures:
    """This month for the marketer home. The current month is never paid."""
    month = current_month()
    split = month_split(db, month, [user.id]).get(user.id, _EMPTY)
    return _figures(month, split, None, settings_service.get_tiers(db))


def _linked_months(db: Session, marketer_id: int) -> set[date]:
    local = func.timezone("Asia/Baghdad", Request.linked_at)
    rows = db.scalars(
        select(func.date_trunc("month", local).cast(Date()))
        .where(
            Request.marketer_id == marketer_id,
            Request.status == "linked",
            Request.deleted_at.is_(None),
        )
        .distinct()
    )
    return set(rows)


def marketer_past_months(db: Session, user: User) -> list[MonthFigures]:
    """Finished months with a linked request or a payment, newest first (FR-007)."""
    payments = {
        p.month: p
        for p in db.scalars(
            select(CommissionPayment).where(CommissionPayment.marketer_id == user.id)
        )
    }
    current = current_month()
    months = sorted(
        (m for m in _linked_months(db, user.id) | set(payments) if m < current), reverse=True
    )
    tiers = settings_service.get_tiers(db)
    return [
        _figures(
            m,
            month_split(db, m, [user.id]).get(user.id, _EMPTY),
            payments.get(m),
            tiers,
        )
        for m in months
    ]
