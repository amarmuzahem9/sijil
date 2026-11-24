"""/api/marketer/* — the marketer home (docs/system.md v1.18 §4.2, specs/013 US2)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.schemas.dashboard import MarketerDashboard
from app.services import link_service

router = APIRouter(prefix="/marketer", tags=["marketer"])


@router.get("/dashboard", response_model=MarketerDashboard)
def dashboard(
    ctx: AuthContext = Depends(require_roles("marketer")),
    db: Session = Depends(get_db),
) -> MarketerDashboard:
    """«تم الربط هذا الشهر»: the caller's links only (Principle IX)."""
    return link_service.marketer_counts(db, ctx.user)
