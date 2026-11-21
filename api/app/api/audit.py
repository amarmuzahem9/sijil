"""/api/admin/audit* — main admin only, read-only (specs/002 contracts/api.md › Audit log)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.errors import AppError
from app.schemas.audit import ActorList, AuditPage
from app.services import audit_query

router = APIRouter(prefix="/admin/audit", tags=["audit"])
_main_admin = require_roles("super_admin")


@router.get("", response_model=AuditPage)
def list_audit(
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    actor_id: str | None = None,
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(audit_query.DEFAULT_LIMIT, ge=1, le=audit_query.MAX_LIMIT),
    _: AuthContext = Depends(_main_admin),
    db: Session = Depends(get_db),
) -> AuditPage:
    actor: int | str | None = None
    if actor_id == audit_query.SYSTEM_ACTOR:
        actor = actor_id
    elif actor_id is not None:
        if not actor_id.isdigit():
            raise AppError("validation_error", 422)
        actor = int(actor_id)
    if from_ and to and from_ > to:
        raise AppError("validation_error", 422)
    return audit_query.list_entries(
        db, from_date=from_, to_date=to, actor=actor, before_id=before_id, limit=limit
    )


@router.get("/actors", response_model=ActorList)
def list_actors(_: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)) -> ActorList:
    return ActorList(items=audit_query.list_actors(db))
