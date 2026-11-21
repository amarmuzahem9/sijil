"""/api/admin/admins* — main admin only (specs/002 contracts/api.md › Admins).

Only rows with role = 'admin' are reachable, so the main admin can never be targeted (R4).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.schemas.accounts import (
    AccountList,
    AccountOut,
    AdminCreate,
    AdminUpdate,
    ResetPasswordBody,
)
from app.services import account_service

router = APIRouter(prefix="/admin/admins", tags=["admins"])
_main_admin = require_roles("super_admin")


@router.get("", response_model=AccountList)
def list_admins(
    _: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> AccountList:
    users = account_service.list_accounts(db, "admin")
    return AccountList(items=[AccountOut.model_validate(u) for u in users])


@router.post("", response_model=AccountOut, status_code=201)
def create_admin(
    body: AdminCreate, ctx: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> AccountOut:
    user = account_service.create_account(
        db,
        ctx.user,
        role="admin",
        name=body.name,
        phone=body.phone,
        temporary_password=body.temporary_password,
        permissions=body.permissions,
    )
    return AccountOut.model_validate(user)


@router.patch("/{user_id}", response_model=AccountOut)
def update_admin(
    user_id: int,
    body: AdminUpdate,
    ctx: AuthContext = Depends(_main_admin),
    db: Session = Depends(get_db),
) -> AccountOut:
    target = account_service.get_target(db, user_id, "admin")
    account_service.ensure_not_protected(target)
    user = account_service.update_account(
        db, ctx.user, target, name=body.name, phone=body.phone, permissions=body.permissions
    )
    return AccountOut.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=AccountOut)
def deactivate_admin(
    user_id: int, ctx: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> AccountOut:
    target = account_service.get_target(db, user_id, "admin")
    return AccountOut.model_validate(account_service.set_active(db, ctx.user, target, False))


@router.post("/{user_id}/reactivate", response_model=AccountOut)
def reactivate_admin(
    user_id: int, ctx: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> AccountOut:
    target = account_service.get_target(db, user_id, "admin")
    return AccountOut.model_validate(account_service.set_active(db, ctx.user, target, True))


@router.post("/{user_id}/reset-password", response_model=AccountOut)
def reset_admin_password(
    user_id: int,
    body: ResetPasswordBody,
    ctx: AuthContext = Depends(_main_admin),
    db: Session = Depends(get_db),
) -> AccountOut:
    target = account_service.get_target(db, user_id, "admin")
    user = account_service.reset_password(db, ctx.user, target, body.temporary_password)
    return AccountOut.model_validate(user)
