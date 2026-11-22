"""/api/admin/archive* — main admin only (specs/003 contracts/api.md, system.md §3.6)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.models import User
from app.schemas.accounts import AccountOut, ArchivedAccountOut, ArchivedList, PersonOut
from app.services import account_service

router = APIRouter(prefix="/admin/archive", tags=["archive"])
_main_admin = require_roles("super_admin")


def _archived_out(db: Session, user: User) -> ArchivedAccountOut:
    by = db.get(User, user.archived_by) if user.archived_by is not None else None
    return ArchivedAccountOut(
        id=user.id,
        name=user.name,
        phone=user.phone,
        role=user.role,
        permissions=user.permissions,
        archived_at=user.archived_at,  # type: ignore[arg-type]
        archived_by=PersonOut(id=by.id, name=by.name, role=by.role) if by else None,
    )


@router.get("", response_model=ArchivedList)
def list_archived(
    _: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> ArchivedList:
    return ArchivedList(items=[_archived_out(db, u) for u in account_service.list_archived(db)])


@router.post("/{user_id}", response_model=AccountOut)
def archive_account(
    user_id: int, ctx: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> AccountOut:
    target = account_service.get_archivable(db, user_id)
    return AccountOut.model_validate(account_service.archive(db, ctx.user, target))


@router.post("/{user_id}/restore", response_model=AccountOut)
def restore_account(
    user_id: int, ctx: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> AccountOut:
    target = account_service.get_archived(db, user_id)
    return AccountOut.model_validate(account_service.restore(db, ctx.user, target))
