"""«تم الربط» (docs/system.md v1.18 §6.5, specs/013 research R1–R3, R7).

The link and its undo run under the request's row lock, through the §7.2 transition check, and
write the request, a `request_links` row, an audit entry and a notification in one transaction:
a refused action writes nothing. The lists carry only what SAS checking needs (`LinkRow`).
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import link_search, request_status, unlink_reasons
from app.core.timeutil import baghdad_month_bounds, baghdad_month_label, utc_now
from app.errors import AppError
from app.models import Request, RequestLink, User
from app.schemas.admin_links import LinkList, LinkRow, UnlinkIn
from app.schemas.dashboard import MarketerDashboard, NextTier, RecentLink
from app.services import audit_service, notification_service

log = logging.getLogger("sijil.links")


# --- rows ----------------------------------------------------------------------------------------


def _current_link_id(db: Session, request: Request) -> int | None:
    """The newest `linked` row of a linked request; None otherwise."""
    if request.status != "linked":
        return None
    return db.scalar(
        select(RequestLink.id)
        .where(RequestLink.request_id == request.id, RequestLink.kind == "linked")
        .order_by(RequestLink.id.desc())
        .limit(1)
    )


def _names(db: Session, ids: set[int | None]) -> dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all())


def _row(db: Session, request: Request, names: dict[int, str]) -> LinkRow:
    return LinkRow(
        id=request.id,
        number_label=request.number_label,
        full_name=request.full_name,
        username=request.username,
        phone=request.phone,
        tower_name=request.tower_name,
        tower_code=request.tower_code,
        plan_name=request.plan_name,
        marketer_name=request.marketer.name,
        approved_at=request.approved_at,
        linked_at=request.linked_at,
        linked_by_name=names.get(request.linked_by) if request.linked_by else None,
        link_id=_current_link_id(db, request),
    )


def to_row(db: Session, request: Request) -> LinkRow:
    return _row(db, request, _names(db, {request.linked_by}))


# --- lists (R7) ----------------------------------------------------------------------------------


def _search(query, q: str):
    if len(q.strip()) < link_search.MIN_LENGTH:
        raise AppError("validation_error", 422)
    term = link_search.classify(q)
    if term is None:
        return query.where(False)
    if term.kind == "number":
        return query.where(Request.number == term.value)
    if term.kind == "phone":
        return query.where(Request.phone == term.value)
    return query.where(func.upper(Request.username) == term.value)


def _page(db: Session, query, order, q: str | None, offset: int, limit: int) -> LinkList:
    if q is not None:
        query = _search(query, q)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(*order).offset(offset).limit(limit)).all()
    names = _names(db, {r.linked_by for r in rows})
    return LinkList(items=[_row(db, r, names) for r in rows], total=total)


def awaiting(db: Session, q: str | None, offset: int, limit: int) -> LinkList:
    """Accepted, not linked, not deleted; the longest waiting first (FR-002)."""
    query = select(Request).where(Request.status == "approved", Request.deleted_at.is_(None))
    return _page(db, query, (Request.approved_at, Request.id), q, offset, limit)


def recent(db: Session, q: str | None, offset: int, limit: int) -> LinkList:
    """Linked, not deleted; the newest link first, every month (FR-004)."""
    query = select(Request).where(Request.status == "linked", Request.deleted_at.is_(None))
    return _page(db, query, (Request.linked_at.desc(), Request.id.desc()), q, offset, limit)


# --- link (R2, R3) -------------------------------------------------------------------------------


def _lock(db: Session, request_id: int) -> Request:
    """The request row under `FOR UPDATE`; a second admin waits and then sees the first change."""
    request = db.scalars(
        select(Request)
        .where(Request.id == request_id)
        # Only the request row: the marketer is joined for display (lazy="joined").
        .with_for_update(of=Request)
        .execution_options(populate_existing=True)
    ).one_or_none()
    if request is None:
        raise AppError("request_not_found", 404)
    # A deleted request keeps its status, so this comes first (specs/011).
    if request.is_deleted:
        raise AppError("request_deleted", 409)
    return request


def link(db: Session, user: User, request_id: int) -> Request:
    request = _lock(db, request_id)
    if request.status == "linked":
        raise AppError("already_linked", 409)
    request_status.check(request.status, "linked")

    now = utc_now()
    request.status = "linked"
    request.linked_at = now
    request.linked_by = user.id
    request.updated_at = now
    db.add(RequestLink(request_id=request.id, kind="linked", actor_id=user.id, at=now))
    audit_service.record(
        db,
        actor_id=user.id,
        action="request.linked",
        entity_type="request",
        entity_id=str(request.number),
        before={"status": "approved"},
        after={"status": "linked"},
    )
    # specs/013 FR-007: in the same transaction, so only an effective link notifies.
    notification_service.add(db, request, "linked")
    db.commit()
    # The action and the number only (constitution Principle II).
    log.info("link number=%s", request.number)
    return request


def unlink(db: Session, user: User, request_id: int, body: UnlinkIn) -> Request:
    """«التراجع عن الربط»: back to accepted, with a reason from the fixed list (FR-008 to FR-010).
    `link_id` must be the current link, so a stale page cannot undo a newer link (R2)."""
    unlink_reasons.validate(body.reason)
    request = _lock(db, request_id)
    if request.status == "approved" or (
        request.status == "linked" and _current_link_id(db, request) != body.link_id
    ):
        raise AppError("already_unlinked", 409)
    # §7.2 also allows pending → approved (acceptance), so the undo names its own source state.
    if request.status != "linked":
        raise AppError("invalid_transition", 409)
    request_status.check(request.status, "approved")

    now = utc_now()
    request.status = "approved"
    request.linked_at = None
    request.linked_by = None
    request.updated_at = now
    db.add(
        RequestLink(
            request_id=request.id, kind="unlinked", actor_id=user.id, at=now, reason=body.reason
        )
    )
    audit_service.record(
        db,
        actor_id=user.id,
        action="request.unlinked",
        entity_type="request",
        entity_id=str(request.number),
        before={"status": "linked"},
        after={"status": "approved", "reason": body.reason},
    )
    notification_service.add(db, request, "unlinked", body.reason)
    db.commit()
    log.info("unlink number=%s reason=%s", request.number, body.reason)
    return request


# --- the marketer home (R5) ----------------------------------------------------------------------

RECENT_LIMIT = 10


def marketer_counts(db: Session, user: User) -> MarketerDashboard:
    """This Baghdad month's links of `user`: counted for commission, without commission, the tier
    and the expected amount (from `commission_service`, so the home and the report share one
    rule, specs/017 R11), and the latest ten. A request has one current `linked_at`, so it counts
    once (FR-012)."""
    from app.services import commission_service

    figures = commission_service.marketer_current(db, user)
    start, end = baghdad_month_bounds()
    this_month = (
        Request.marketer_id == user.id,
        Request.status == "linked",
        Request.deleted_at.is_(None),
        Request.linked_at >= start,
        Request.linked_at < end,
    )
    recent = db.scalars(
        select(Request)
        .where(*this_month)
        .order_by(Request.linked_at.desc(), Request.id.desc())
        .limit(RECENT_LIMIT)
    ).all()
    return MarketerDashboard(
        linked_this_month=figures.count,
        linked_without_commission=figures.without_commission,
        month_label=baghdad_month_label(),
        tier_rate=figures.rate,
        expected_amount=figures.amount,
        next_tier=(
            NextTier(remaining=figures.next_tier[0], rate=figures.next_tier[1])
            if figures.next_tier
            else None
        ),
        recent_links=[
            RecentLink(
                id=r.id, number_label=r.number_label, full_name=r.full_name, linked_at=r.linked_at
            )
            for r in recent
        ],
    )
