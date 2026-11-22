"""/api/catalog — any signed-in user (FR-014, specs/004 research R3).

Only what the new-request form may offer: active areas, active towers of active areas, active plans.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, current_user
from app.db import get_db
from app.schemas.settings import Catalog, CatalogArea, CatalogPlan, CatalogTower
from app.services import settings_service

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=Catalog)
def get_catalog(_: AuthContext = Depends(current_user), db: Session = Depends(get_db)) -> Catalog:
    areas, towers, plans = settings_service.catalog(db)
    return Catalog(
        areas=[CatalogArea(id=a.id, name=a.name) for a in areas],
        towers=[CatalogTower(id=t.id, code=t.code, name=t.name, area_id=t.area_id) for t in towers],
        plans=[
            CatalogPlan(
                id=p.id, name=p.name, trial_price=p.trial_price, second_price=p.second_price
            )
            for p in plans
        ],
    )
