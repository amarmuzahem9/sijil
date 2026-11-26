"""/api/admin/commissions/* — «العمولات» (docs/system.md v1.23 §9, §10 item 13; specs/017
contracts/api.md).

Every route needs the main admin or an admin with `commissions`, checked on the server
(Principle IX). The rows and details are allow-lists without identity data (research R9).
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.core import commission
from app.db import get_db
from app.errors import AppError
from app.models import Request
from app.schemas.commissions import (
    AlertOut,
    DetailLine,
    DetailOut,
    MonthList,
    PaidBeforeLine,
    PayIn,
    PaymentOut,
    ReportOut,
    ReportRowOut,
)
from app.services import commission_service
from app.services.commission_service import ReportRow

router = APIRouter(prefix="/admin/commissions", tags=["admin-commissions"])

commissions_only = require_permission("commissions")


def _month(value: str) -> date:
    """`YYYY-MM`, not after the current Baghdad month; else 422."""
    try:
        month = commission.parse_month(value)
    except ValueError:
        raise AppError("validation_error", 422) from None
    if month > commission_service.current_month():
        raise AppError("validation_error", 422)
    return month


def _row_out(row: ReportRow) -> ReportRowOut:
    f = row.figures
    return ReportRowOut(
        marketer_id=row.marketer.id,
        marketer_name=row.marketer.name,
        count=f.count,
        without_commission=f.without_commission - row.paid_before,
        paid_before=row.paid_before,
        tier_min_count=f.tier_min_count,
        rate=f.rate,
        amount=f.amount,
        payable=row.payable,
        payment=(
            PaymentOut(
                paid_by_name=row.paid_by_name,
                paid_at=f.payment.paid_at,
                count_today=row.count_today,
            )
            if f.payment is not None
            else None
        ),
        alerts=[
            AlertOut(number_label=a.number_label, at=a.at, reason=a.reason) for a in row.alerts
        ],
    )


def _line(request: Request) -> DetailLine:
    return DetailLine(
        id=request.id,
        number_label=request.number_label,
        full_name=request.full_name,
        type=request.type,
        tower_name=request.tower_name,
        tower_code=request.tower_code,
        linked_at=request.linked_at,
    )


@router.get("/months", response_model=MonthList)
def list_months(
    _: AuthContext = Depends(commissions_only), db: Session = Depends(get_db)
) -> MonthList:
    return MonthList(
        items=[commission.month_key(m) for m in commission_service.months(db)],
        current=commission.month_key(commission_service.current_month()),
    )


@router.get("", response_model=ReportOut)
def month_report(
    month: str = Query(max_length=7),
    _: AuthContext = Depends(commissions_only),
    db: Session = Depends(get_db),
) -> ReportOut:
    """One row per marketer with a linked request or a payment in the month (FR-009)."""
    m = _month(month)
    rows = [_row_out(r) for r in commission_service.report(db, m)]
    return ReportOut(
        month=commission.month_key(m),
        month_label=commission_service.month_label(m),
        finished=m < commission_service.current_month(),
        total_amount=sum(r.amount for r in rows),
        rows=rows,
    )


@router.get("/{month}/marketers/{marketer_id}", response_model=DetailOut)
def row_detail(
    month: str,
    marketer_id: int,
    _: AuthContext = Depends(commissions_only),
    db: Session = Depends(get_db),
) -> DetailOut:
    """The requests behind a row (FR-010); 404 when the marketer has no row in that month."""
    lists = commission_service.detail(db, _month(month), marketer_id)
    return DetailOut(
        counted=[_line(r) for r in lists.counted],
        without_commission=[_line(r) for r in lists.without_commission],
        paid_before=[
            PaidBeforeLine(**_line(r).model_dump(), paid_month=commission.month_key(paid))
            for r, paid in lists.paid_before
        ],
    )


@router.post("/{month}/marketers/{marketer_id}/pay", response_model=ReportRowOut)
def pay_month(
    month: str,
    marketer_id: int,
    body: PayIn,
    ctx: AuthContext = Depends(commissions_only),
    db: Session = Depends(get_db),
) -> ReportRowOut:
    """«تم الدفع» (FR-011, FR-012). 409 `month_not_finished`, `nothing_to_pay`,
    `commission_changed` or `already_paid`; nothing is written then. No route edits or removes a
    payment (FR-013)."""
    row = commission_service.pay(db, ctx.user, _month(month), marketer_id, body.count, body.amount)
    return _row_out(row)
