"""The admin home counts (docs/system.md v1.13 §10 item 1, specs/010 research R10).

Each count goes by the time of its own step, in Baghdad days and months: submitted by
`submitted_at`, approved by `approved_at` (the automatic approval counts at submission), rejected
by `rejected_at`. Pending is the current number, the same in both rows. Linked stays 0 until 012
adds `linked_at`. Counts only: no subscriber data.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import baghdad_month_bounds, baghdad_today_bounds
from app.models import Request
from app.schemas.admin_requests import HomeCounts, HomeOut


def _count(db: Session, column, start: datetime, end: datetime) -> int:
    return db.scalar(select(func.count()).select_from(Request).where(column >= start, column < end))


def _row(db: Session, bounds: tuple[datetime, datetime], pending: int) -> HomeCounts:
    start, end = bounds
    return HomeCounts(
        submitted=_count(db, Request.submitted_at, start, end),
        approved=_count(db, Request.approved_at, start, end),
        pending=pending,
        linked=0,
        rejected=_count(db, Request.rejected_at, start, end),
    )


def counts(db: Session) -> HomeOut:
    pending = db.scalar(
        select(func.count()).select_from(Request).where(Request.status == "pending_review")
    )
    return HomeOut(
        today=_row(db, baghdad_today_bounds(), pending),
        month=_row(db, baghdad_month_bounds(), pending),
    )
