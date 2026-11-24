"""Notifications to the marketer (docs/system.md v1.17 §4.4, specs/012 research R5–R7).

`add` is called by the decision services inside their own transaction, before their commit, so a
refused decision never writes one and an accepted one always does. The row holds no personal data;
`page` reads the subscriber's name from the request, which a deletion (011) has set to null.
Feature 013 calls `add(..., "linked")` and `add(..., "unlinked", <code>)` and adds its undo reason
labels to `_REASON_LABELS`.
"""

import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import deletion_reasons, rejection_reasons
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models.notification import Notification
from app.models.request import Request
from app.models.user import User
from app.schemas.notifications import NotificationOut, NotificationPage

log = logging.getLogger("sijil.notifications")

# The label of a reason code, by kind; never the reviewer's own note.
_REASON_LABELS: dict[str, dict[str, str]] = {
    "rejected": rejection_reasons.LABELS,
    "deleted": deletion_reasons.LABELS,
}


def add(db: Session, request: Request, kind: str, reason: str | None = None) -> Notification:
    """A new notification for the request's marketer. Flushed, not committed."""
    row = Notification(
        marketer_id=request.marketer_id,
        request_id=request.id,
        kind=kind,
        reason=reason,
        created_at=utc_now(),
    )
    db.add(row)
    db.flush()
    # The kind and the request number only (constitution Principle II).
    log.info("notification %s number=%s", kind, request.number)
    return row


def _reason_label(row: Notification) -> str | None:
    if row.reason is None:
        return None
    return _REASON_LABELS.get(row.kind, {}).get(row.reason)


def _out(row: Notification) -> NotificationOut:
    request = row.request
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        request_id=row.request_id,
        number_label=request.number_label,
        full_name=None if request.is_deleted else request.full_name,
        deleted=request.is_deleted,
        reason_label=_reason_label(row),
        created_at=row.created_at,
        read_at=row.read_at,
    )


def page(db: Session, user: User, before: int | None, limit: int) -> NotificationPage:
    """Newest first. `next_before` is the last id when more rows follow, else None."""
    query = select(Notification).where(Notification.marketer_id == user.id)
    if before is not None:
        query = query.where(Notification.id < before)
    rows = db.scalars(query.order_by(Notification.id.desc()).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return NotificationPage(
        items=[_out(r) for r in rows],
        next_before=rows[-1].id if more else None,
    )


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.marketer_id == user.id, Notification.read_at.is_(None))
    )


def mark_read(db: Session, user: User, notification_id: int) -> None:
    row = db.get(Notification, notification_id)
    if row is None or row.marketer_id != user.id:
        raise AppError("notification_not_found", 404)
    if row.read_at is None:
        row.read_at = utc_now()
        db.commit()


def mark_all(db: Session, user: User) -> None:
    db.execute(
        update(Notification)
        .where(Notification.marketer_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utc_now())
    )
    db.commit()
