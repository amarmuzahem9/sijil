"""/api/admin/admins* — main admin only (specs/002 contracts/api.md › Admins).

Only rows with role = 'admin' are reachable, so the main admin can never be targeted (R4).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.schemas.accounts import AccountList, AccountOut, AdminCreate
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


# PATCH / deactivate / reactivate / reset-password for admins arrive with US3 (T031).
