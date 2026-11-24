"""/api/admin/links/* and the link actions — «بانتظار الربط» (specs/013 contracts/api.md).

Every route needs the main admin or an admin with `link`, checked on the server (Principle IX);
anyone else gets 403.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.db import get_db
from app.schemas.admin_links import LinkList, LinkRow, UnlinkIn
from app.services import link_service

router = APIRouter(prefix="/admin", tags=["admin-links"])

link_only = require_permission("link")


@router.get("/links/awaiting", response_model=LinkList)
def list_awaiting(
    q: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: AuthContext = Depends(link_only),
    db: Session = Depends(get_db),
) -> LinkList:
    """Accepted, not linked; oldest acceptance first. `q`: number, phone or username."""
    return link_service.awaiting(db, q, offset, limit)


@router.get("/links/recent", response_model=LinkList)
def list_recent(
    q: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _: AuthContext = Depends(link_only),
    db: Session = Depends(get_db),
) -> LinkList:
    """Linked; newest link first, every month. Each row carries its current `link_id`."""
    return link_service.recent(db, q, offset, limit)


@router.post("/requests/{request_id}/link", response_model=LinkRow)
def link_request(
    request_id: int,
    ctx: AuthContext = Depends(link_only),
    db: Session = Depends(get_db),
) -> LinkRow:
    """«تم الربط». 409 `already_linked`, `request_deleted` or `invalid_transition`."""
    request = link_service.link(db, ctx.user, request_id)
    return link_service.to_row(db, request)


@router.post("/requests/{request_id}/unlink", response_model=LinkRow)
def unlink_request(
    request_id: int,
    body: UnlinkIn,
    ctx: AuthContext = Depends(link_only),
    db: Session = Depends(get_db),
) -> LinkRow:
    """«التراجع عن الربط». 409 `already_unlinked`, `request_deleted` or `invalid_transition`."""
    request = link_service.unlink(db, ctx.user, request_id, body)
    return link_service.to_row(db, request)
