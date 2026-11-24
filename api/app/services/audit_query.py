"""Read-only audit listing for the main admin (specs/002 research R6): newest first, keyset."""

from datetime import date

from sqlalchemy import String, and_, cast, select
from sqlalchemy.orm import Session, aliased

from app.core.timeutil import baghdad_day_bounds
from app.models import Area, AuditLog, Plan, Request, Tower, User
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
    labels = _settings_labels(db, [entry for entry, _, _ in page])
    deleted = _deleted_requests(db, [entry for entry, _, _ in page])
    items = [
        AuditEntryOut(
            id=entry.id,
            created_at=entry.created_at,
            action=entry.action,
            actor=_person(who),
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            target=_person(whom),
            target_label=labels.get((entry.entity_type, entry.entity_id)),
            before=entry.before,
            after=entry.after,
            entity_deleted=entry.entity_type == "request" and entry.entity_id in deleted,
        )
        for entry, who, whom in page
    ]
    has_more = len(rows) > limit
    return AuditPage(
        items=items, has_more=has_more, next_before_id=items[-1].id if has_more else None
    )


def _deleted_requests(db: Session, entries: list[AuditLog]) -> set[str]:
    """Request numbers (as audited, `entity_id`) in the page whose request is deleted."""
    numbers = {
        int(e.entity_id) for e in entries if e.entity_type == "request" and e.entity_id.isdigit()
    }
    if not numbers:
        return set()
    rows = db.scalars(
        select(Request.number).where(Request.number.in_(numbers), Request.deleted_at.is_not(None))
    )
    return {str(n) for n in rows}


# Settings entries store only the changed fields, so the item's name is looked up here.
_LABEL_COLUMNS = {
    "area": (Area, Area.name),
    "tower": (Tower, Tower.code),
    "plan": (Plan, Plan.name),
}


def _settings_labels(db: Session, entries: list[AuditLog]) -> dict[tuple[str, str], str]:
    """Current label of each settings item in the page; deleted items fall back to `before`."""
    labels: dict[tuple[str, str], str] = {}
    for entity_type, (model, column) in _LABEL_COLUMNS.items():
        ids = {
            int(e.entity_id)
            for e in entries
            if e.entity_type == entity_type and e.entity_id.isdigit()
        }
        if not ids:
            continue
        for item_id, label in db.execute(select(model.id, column).where(model.id.in_(ids))).all():
            labels[(entity_type, str(item_id))] = label
    key_field = {"area": "name", "tower": "code", "plan": "name"}
    for e in entries:
        key = (e.entity_type, e.entity_id)
        if e.entity_type in key_field and key not in labels:
            stored = (e.before or {}).get(key_field[e.entity_type]) or (e.after or {}).get(
                key_field[e.entity_type]
            )
            if isinstance(stored, str):
                labels[key] = stored
    return labels


def list_actors(db: Session) -> list[ActorOut]:
    ids = select(AuditLog.actor_id).where(AuditLog.actor_id.is_not(None)).distinct()
    users = db.execute(select(User).where(User.id.in_(ids)).order_by(User.name)).scalars()
    return [ActorOut(id=u.id, name=u.name, role=u.role) for u in users]
