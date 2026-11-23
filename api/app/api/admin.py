"""/api/admin/* — the admin shell (feature 001) and the admin home counts (specs/010 FR-021)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.schemas.admin_requests import HomeOut
from app.services import admin_home

router = APIRouter(prefix="/admin", tags=["admin"])

any_admin = require_roles("super_admin", "admin")


@router.get("/ping")
def ping(_: AuthContext = Depends(any_admin)) -> dict[str, bool]:
    return {"ok": True}


@router.get("/home", response_model=HomeOut)
def home(_: AuthContext = Depends(any_admin), db: Session = Depends(get_db)) -> HomeOut:
    """Today and this month in Baghdad time, for every admin (research R10). Counts only."""
    return admin_home.counts(db)
