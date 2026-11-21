"""Read-only audit listing for the main admin (specs/002 research R6): newest first, keyset."""

from datetime import date

from sqlalchemy import String, and_, cast, select
from sqlalchemy.orm import Session, aliased

from app.core.timeutil import baghdad_day_bounds
from app.models import AuditLog, User
from app.schemas.audit import ActorOut, AuditEntryOut, AuditPage

DEFAULT_LIMIT, MAX_LIMIT = 50, 100
SYSTEM_ACTOR = "system"


def _person(user: User | None) -> ActorOut | None:
    return ActorOut(id=user.id, name=user.name, role=user.role) if user is not None else None


def list_entries(
    db: Session,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    actor: int | str | None = None,
    before_id: int | None = None,
    limit: int = DEFAULT_LIMIT,
) -> AuditPage:
    limit = max(1, min(limit, MAX_LIMIT))
    actor_user = aliased(User)
    target_user = aliased(User)
    query = (
        select(AuditLog, actor_user, target_user)
        .outerjoin(actor_user, actor_user.id == AuditLog.actor_id)
        .outerjoin(
            target_user,
            and_(
                AuditLog.entity_type == "user", cast(target_user.id, String) == AuditLog.entity_id
            ),
        )
        .order_by(AuditLog.id.desc())
        .limit(limit + 1)
    )
    start, end = baghdad_day_bounds(from_date, to_date)
    if start is not None:
        query = query.where(AuditLog.created_at >= start)
    if end is not None:
        query = query.where(AuditLog.created_at < end)
    if actor == SYSTEM_ACTOR:
        query = query.where(AuditLog.actor_id.is_(None))
    elif actor is not None:
        query = query.where(AuditLog.actor_id == int(actor))
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)

    rows = db.execute(query).all()
    page = rows[:limit]
    items = [
        AuditEntryOut(
            id=entry.id,
            created_at=entry.created_at,
            action=entry.action,
            actor=_person(who),
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            target=_person(whom),
            before=entry.before,
            after=entry.after,
        )
        for entry, who, whom in page
    ]
    has_more = len(rows) > limit
    return AuditPage(
        items=items, has_more=has_more, next_before_id=items[-1].id if has_more else None
    )


def list_actors(db: Session) -> list[ActorOut]:
    ids = select(AuditLog.actor_id).where(AuditLog.actor_id.is_not(None)).distinct()
    users = db.execute(select(User).where(User.id.in_(ids)).order_by(User.name)).scalars()
    return [ActorOut(id=u.id, name=u.name, role=u.role) for u in users]
