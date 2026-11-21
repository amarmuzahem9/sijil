"""/api/marketer/* — marketer dashboard skeleton (feature 001)."""

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, require_roles
from app.core.timeutil import baghdad_month_label

router = APIRouter(prefix="/marketer", tags=["marketer"])


@router.get("/dashboard")
def dashboard(_: AuthContext = Depends(require_roles("marketer"))) -> dict[str, int | str]:
    # The linked counter is a fixed 0 until feature 011 (docs/system.md §6.5).
    return {"linked_this_month": 0, "month_label": baghdad_month_label()}
