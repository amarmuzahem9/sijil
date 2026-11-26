"""/api/marketer/* — the marketer home and past months (docs/system.md v1.23 §4.2, specs/013 US2,
specs/017 US1)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.core import commission
from app.db import get_db
from app.schemas.commissions import PastMonth, PastMonths
from app.schemas.dashboard import MarketerDashboard
from app.services import commission_service, link_service

router = APIRouter(prefix="/marketer", tags=["marketer"])


@router.get("/dashboard", response_model=MarketerDashboard)
def dashboard(
    ctx: AuthContext = Depends(require_roles("marketer")),
    db: Session = Depends(get_db),
) -> MarketerDashboard:
    """«تم الربط هذا الشهر»: the caller's links only (Principle IX)."""
    return link_service.marketer_counts(db, ctx.user)


@router.get("/commissions/months", response_model=PastMonths)
def past_months(
    ctx: AuthContext = Depends(require_roles("marketer")),
    db: Session = Depends(get_db),
) -> PastMonths:
    """«الأشهر السابقة»: the caller's finished months only (specs/017 FR-007, Principle IX)."""
    return PastMonths(
        items=[
            PastMonth(
                month=commission.month_key(f.month),
                month_label=commission_service.month_label(f.month),
                count=f.count,
                without_commission=f.without_commission,
                rate=f.rate,
                amount=f.amount,
                paid=f.payment is not None,
            )
            for f in commission_service.marketer_past_months(db, ctx.user)
        ]
    )
