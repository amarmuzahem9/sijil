"""Commissions (docs/system.md v1.23 §9, specs/017 research R2–R7).

One count rule serves the marketer home, the past months, the report and the marketers page:
a marketer month is their requests linked now, not deleted, whose current link falls in the
Baghdad month. Each is `counted`, `without_commission` (a return accepted with «لا») or
`paid_before` (already in a payment, owner Q1). Legacy and SAS subscribers are not requests and
have no marketer, so they never enter it.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import Date, case, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import commission
from app.core.timeutil import BAGHDAD, baghdad_month_bounds, baghdad_month_label, utc_now
from app.errors import AppError
from app.models import CommissionPayment, CommissionPaymentRequest, Request, User
from app.services import audit_service, settings_service

log = logging.getLogger("sijil.commissions")


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


# --- the admin report (research R4, R6, R7, R9) --------------------------------------------------


@dataclass(frozen=True)
class ReportRow:
    marketer: User
    figures: MonthFigures
    paid_before: int
    payable: bool
    paid_by_name: str | None
    count_today: int | None


def months(db: Session) -> list[date]:
    """Every Baghdad month from the earliest link or payment to the current one, newest first."""
    local = func.timezone("Asia/Baghdad", Request.linked_at)
    first_link = db.scalar(
        select(func.min(func.date_trunc("month", local).cast(Date()))).where(
            Request.status == "linked", Request.deleted_at.is_(None)
        )
    )
    first_paid = db.scalar(select(func.min(CommissionPayment.month)))
    current = current_month()
    start = min(m for m in (first_link, first_paid, current) if m is not None)
    out = []
    m = current
    while m >= start:
        out.append(m)
        m = (m.replace(day=1) - timedelta(days=1)).replace(day=1)
    return out


def _payments(db: Session, month: date, marketer_ids=None) -> dict[int, CommissionPayment]:
    query = select(CommissionPayment).where(CommissionPayment.month == month)
    if marketer_ids is not None:
        query = query.where(CommissionPayment.marketer_id.in_(list(marketer_ids)))
    return {p.marketer_id: p for p in db.scalars(query)}


def _count_today(db: Session, payment: CommissionPayment) -> int:
    """The payment's requests still linked in its month: lower after an undo (research R4)."""
    return db.scalar(
        select(func.count())
        .select_from(CommissionPaymentRequest)
        .join(Request, Request.id == CommissionPaymentRequest.request_id)
        .where(CommissionPaymentRequest.payment_id == payment.id, *_in_month(payment.month))
    )


def _rows(db: Session, month: date, marketer_ids=None) -> list[ReportRow]:
    splits = month_split(db, month, marketer_ids)
    payments = _payments(db, month, marketer_ids)
    ids = set(splits) | set(payments)
    if not ids:
        return []
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))}
    payers = {
        u.id: u.name
        for u in db.scalars(select(User).where(User.id.in_({p.paid_by for p in payments.values()})))
    }
    tiers = settings_service.get_tiers(db)
    finished = month < current_month()
    rows = []
    for marketer_id in ids:
        split = splits.get(marketer_id, _EMPTY)
        payment = payments.get(marketer_id)
        figures = _figures(month, split, payment, tiers)
        rows.append(
            ReportRow(
                marketer=users[marketer_id],
                figures=figures,
                paid_before=split.paid_before,
                payable=finished and payment is None and figures.count > 0,
                paid_by_name=payers.get(payment.paid_by) if payment else None,
                count_today=_count_today(db, payment) if payment else None,
            )
        )
    return sorted(rows, key=lambda r: (r.marketer.name, r.marketer.id))


def report(db: Session, month: date) -> list[ReportRow]:
    """One row per marketer with a linked request or a payment in the month (FR-009)."""
    return _rows(db, month)


def report_row(db: Session, month: date, marketer_id: int) -> ReportRow:
    rows = _rows(db, month, [marketer_id])
    if not rows:
        raise AppError("not_found", 404)
    return rows[0]


@dataclass(frozen=True)
class DetailLists:
    counted: list[Request]
    without_commission: list[Request]
    # (request, the month it was paid in)
    paid_before: list[tuple[Request, date]]


def detail(db: Session, month: date, marketer_id: int) -> DetailLists:
    """The requests behind a row (FR-010). A paid row lists the requests stored at payment."""
    report_row(db, month, marketer_id)  # 404 when there is no row
    payment = _payments(db, month, [marketer_id]).get(marketer_id)
    in_month = db.scalars(
        select(Request)
        .where(Request.marketer_id == marketer_id, *_in_month(month))
        .order_by(Request.linked_at, Request.id)
    ).all()
    paid_months = dict(
        db.execute(
            select(CommissionPaymentRequest.request_id, CommissionPayment.month)
            .join(CommissionPayment, CommissionPayment.id == CommissionPaymentRequest.payment_id)
            .where(CommissionPaymentRequest.request_id.in_([r.id for r in in_month]))
        ).all()
    )
    if payment is not None:
        counted = db.scalars(
            select(Request)
            .join(CommissionPaymentRequest, CommissionPaymentRequest.request_id == Request.id)
            .where(CommissionPaymentRequest.payment_id == payment.id)
            .order_by(Request.id)
        ).all()
    else:
        counted = [r for r in in_month if r.id not in paid_months and r.counts_commission]
    return DetailLists(
        counted=list(counted),
        without_commission=[
            r for r in in_month if r.id not in paid_months and not r.counts_commission
        ],
        paid_before=[
            (r, paid_months[r.id])
            for r in in_month
            if r.id in paid_months and paid_months[r.id] != month
        ],
    )


# --- «تم الدفع» (research R5, R10) ----------------------------------------------------------------


def pay(
    db: Session, admin: User, month: date, marketer_id: int, count: int, amount: int
) -> ReportRow:
    """Lock a finished month of one marketer at the figures the admin confirmed (FR-011, FR-012).

    The counted requests are locked `FOR UPDATE`, the same row lock as «التراجع عن الربط», so an
    undo either lands before (the figures differ: `commission_changed`) or after (an alert). A
    refused call writes nothing; a second payment hits the unique key (`already_paid`)."""
    if month >= current_month():
        raise AppError("month_not_finished", 409)
    marketer = db.get(User, marketer_id)
    if marketer is None or marketer.role != "marketer":
        raise AppError("not_found", 404)
    if _payments(db, month, [marketer_id]):
        raise AppError("already_paid", 409)

    counted = db.scalars(
        select(Request)
        .where(
            Request.marketer_id == marketer_id,
            *_in_month(month),
            ~_paid_in(None),
            Request.counts_commission.is_(True),
        )
        .order_by(Request.id)
        .with_for_update(of=Request)
    ).all()
    # A second admin waited on those row locks: by now the first payment is visible to this new
    # statement (READ COMMITTED), and its requests left the locked set.
    if _payments(db, month, [marketer_id]):
        raise AppError("already_paid", 409)
    n = len(counted)
    if n == 0:
        raise AppError("nothing_to_pay", 409)
    tiers = settings_service.get_tiers(db)
    tier_min, rate = commission.tier_for(n, tiers)
    total = rate * n
    if (count, amount) != (n, total):
        raise AppError("commission_changed", 409)

    payment = CommissionPayment(
        marketer_id=marketer_id,
        month=month,
        count=n,
        tier_min_count=tier_min,
        rate=rate,
        amount=total,
        paid_by=admin.id,
        paid_at=utc_now(),
    )
    try:
        with db.begin_nested():
            db.add(payment)
            db.flush()
            db.add_all(
                CommissionPaymentRequest(request_id=r.id, payment_id=payment.id) for r in counted
            )
            db.flush()
    except IntegrityError:
        # Another admin paid the same row (or one of its requests) first.
        raise AppError("already_paid", 409) from None
    key = commission.month_key(month)
    audit_service.record(
        db,
        actor_id=admin.id,
        action="commission.paid",
        entity_type="commission_payment",
        entity_id=f"{marketer_id}:{key}",
        after={
            "marketer_id": marketer_id,
            "month": key,
            "count": n,
            "tier_min_count": tier_min,
            "rate": rate,
            "amount": total,
        },
    )
    db.commit()
    # Marketer id, month and amount only (constitution Principle II).
    log.info("commission paid marketer=%s month=%s amount=%s", marketer_id, key, total)
    return report_row(db, month, marketer_id)
