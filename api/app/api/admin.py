"""/api/admin/* — admin shell placeholder (feature 001)."""

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, require_roles

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
def ping(_: AuthContext = Depends(require_roles("super_admin", "admin"))) -> dict[str, bool]:
    return {"ok": True}
