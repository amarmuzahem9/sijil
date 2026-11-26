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

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session

from app.core.timeutil import BAGHDAD, baghdad_month_bounds
from app.models import CommissionPaymentRequest, Request


@dataclass(frozen=True)
class MonthSplit:
    counted: int
    without_commission: int
    paid_before: int


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


def _paid_before():
    return exists().where(CommissionPaymentRequest.request_id == Request.id)


def _category():
    return case(
        (_paid_before(), "paid_before"),
        (Request.counts_commission.is_(False), "without_commission"),
        else_="counted",
    )


def month_split(
    db: Session, month: date, marketer_ids: Iterable[int] | None = None
) -> dict[int, MonthSplit]:
    """Per marketer with at least one linked request in the month (research R2).

    For an unpaid month only: a paid month's own requests are in a payment too, so its figures
    come from the payment, never from here (research R4)."""
    category = _category().label("category")
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
        )
        for marketer_id, n in numbers.items()
    }
