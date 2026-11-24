"""/api/notifications: the marketer's own notifications (specs/012 contracts/api.md).

Marketer-only; every call reads or changes the caller's rows only, and another marketer's id
answers 404 (constitution Principle IX).
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.schemas.notifications import NotificationPage, UnreadCount
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

marketer_only = require_roles("marketer")


@router.get("", response_model=NotificationPage)
def list_notifications(
    before: int | None = Query(default=None, ge=1),
    limit: int = Query(default=30, ge=1, le=50),
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> NotificationPage:
    """Newest first; pass `next_before` back as `before` for older ones."""
    return notification_service.page(db, ctx.user, before, limit)


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> UnreadCount:
    return UnreadCount(count=notification_service.unread_count(db, ctx.user))


@router.post("/read-all", status_code=204)
def read_all(
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> Response:
    notification_service.mark_all(db, ctx.user)
    return Response(status_code=204)


@router.post("/{notification_id}/read", status_code=204)
def read_one(
    notification_id: int,
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> Response:
    notification_service.mark_read(db, ctx.user, notification_id)
    return Response(status_code=204)
