"""/api/admin/marketers* — `marketers` permission or main admin (specs/002 contracts/api.md).

Only rows with role = 'marketer' are reachable, so admin accounts never are (FR-012).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.db import get_db
from app.schemas.accounts import (
    AccountList,
    AccountOut,
    MarketerCreate,
    MarketerUpdate,
    ResetPasswordBody,
)
from app.schemas.commissions import MonthSummary, MonthSummaryItem
from app.services import account_service, commission_service

router = APIRouter(prefix="/admin/marketers", tags=["marketers"])
_can_manage = require_permission("marketers")


@router.get("", response_model=AccountList)
def list_marketers(
    _: AuthContext = Depends(_can_manage), db: Session = Depends(get_db)
) -> AccountList:
    users = account_service.list_accounts(db, "marketer")
    return AccountList(items=[AccountOut.model_validate(u) for u in users])


@router.get("/month-summary", response_model=MonthSummary)
def month_summary(
    _: AuthContext = Depends(_can_manage), db: Session = Depends(get_db)
) -> MonthSummary:
    """This month's count and expected commission per marketer, without payment (specs/017
    FR-019). Same rule as the marketer home."""
    return MonthSummary(
        month_label=commission_service.month_label(commission_service.current_month()),
        items=[
            MonthSummaryItem(marketer_id=m, count=c, amount=a)
            for m, c, a in commission_service.month_summary(db)
        ],
    )


@router.post("", response_model=AccountOut, status_code=201)
def create_marketer(
    body: MarketerCreate, ctx: AuthContext = Depends(_can_manage), db: Session = Depends(get_db)
) -> AccountOut:
    user = account_service.create_account(
        db,
        ctx.user,
        role="marketer",
        name=body.name,
        phone=body.phone,
        temporary_password=body.temporary_password,
    )
    return AccountOut.model_validate(user)


@router.patch("/{user_id}", response_model=AccountOut)
def update_marketer(
    user_id: int,
    body: MarketerUpdate,
    ctx: AuthContext = Depends(_can_manage),
    db: Session = Depends(get_db),
) -> AccountOut:
    target = account_service.get_target(db, user_id, "marketer")
    user = account_service.update_account(db, ctx.user, target, name=body.name, phone=body.phone)
    return AccountOut.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=AccountOut)
def deactivate_marketer(
    user_id: int, ctx: AuthContext = Depends(_can_manage), db: Session = Depends(get_db)
) -> AccountOut:
    target = account_service.get_target(db, user_id, "marketer")
    return AccountOut.model_validate(account_service.set_active(db, ctx.user, target, False))


@router.post("/{user_id}/reactivate", response_model=AccountOut)
def reactivate_marketer(
    user_id: int, ctx: AuthContext = Depends(_can_manage), db: Session = Depends(get_db)
) -> AccountOut:
    target = account_service.get_target(db, user_id, "marketer")
    return AccountOut.model_validate(account_service.set_active(db, ctx.user, target, True))


@router.post("/{user_id}/reset-password", response_model=AccountOut)
def reset_marketer_password(
    user_id: int,
    body: ResetPasswordBody,
    ctx: AuthContext = Depends(_can_manage),
    db: Session = Depends(get_db),
) -> AccountOut:
    target = account_service.get_target(db, user_id, "marketer")
    user = account_service.reset_password(db, ctx.user, target, body.temporary_password)
    return AccountOut.model_validate(user)
