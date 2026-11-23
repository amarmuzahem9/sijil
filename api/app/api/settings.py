"""/api/admin/settings/* — `settings` permission or main admin (specs/004 contracts/api.md)."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.db import get_db
from app.models import Area, Plan, Tower
from app.schemas.settings import (
    AreaCreate,
    AreaOut,
    AreaRef,
    AreaUpdate,
    GeneralOut,
    GeneralUpdate,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    TierOut,
    TiersBody,
    TiersOut,
    TowerCreate,
    TowerOut,
    TowerUpdate,
)
from app.services import settings_service as svc

router = APIRouter(prefix="/admin/settings", tags=["settings"])
_can = require_permission("settings")


def _area_out(db: Session, area: Area) -> AreaOut:
    count = svc.usage_count(db, "area", area.id)
    towers = svc._area_tower_count(db, area.id)
    return AreaOut(
        id=area.id, name=area.name, is_active=area.is_active, in_use=count > 0, tower_count=towers
    )


def _tower_out(tower: Tower, used: bool) -> TowerOut:
    return TowerOut(
        id=tower.id,
        code=tower.code,
        name=tower.name,
        area=AreaRef(id=tower.area.id, name=tower.area.name, is_active=tower.area.is_active),
        is_active=tower.is_active,
        in_use=used,
    )


def _plan_out(plan: Plan, used: bool) -> PlanOut:
    return PlanOut(
        id=plan.id,
        name=plan.name,
        trial_price=plan.trial_price,
        second_price=plan.second_price,
        is_active=plan.is_active,
        in_use=used,
    )


# --- areas --------------------------------------------------------------------------------------


@router.get("/areas")
def list_areas(_: AuthContext = Depends(_can), db: Session = Depends(get_db)) -> dict:
    return {
        "items": [
            AreaOut(id=a.id, name=a.name, is_active=a.is_active, in_use=used, tower_count=n)
            for a, n, used in svc.list_areas(db)
        ]
    }


@router.post("/areas", response_model=AreaOut, status_code=201)
def create_area(
    body: AreaCreate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> AreaOut:
    return _area_out(db, svc.create_area(db, ctx.user, body.name))


@router.patch("/areas/{item_id}", response_model=AreaOut)
def update_area(
    item_id: int, body: AreaUpdate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> AreaOut:
    area = svc.get_item(db, "area", item_id)
    return _area_out(db, svc.update_area(db, ctx.user, area, body.name))


# --- towers -------------------------------------------------------------------------------------


@router.get("/towers")
def list_towers(_: AuthContext = Depends(_can), db: Session = Depends(get_db)) -> dict:
    return {"items": [_tower_out(t, used) for t, used in svc.list_towers(db)]}


@router.post("/towers", response_model=TowerOut, status_code=201)
def create_tower(
    body: TowerCreate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> TowerOut:
    tower = svc.create_tower(db, ctx.user, body.code, body.name, body.area_id)
    return _tower_out(tower, svc.in_use(db, "tower", tower.id))


@router.patch("/towers/{item_id}", response_model=TowerOut)
def update_tower(
    item_id: int, body: TowerUpdate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> TowerOut:
    tower = svc.get_item(db, "tower", item_id)
    tower = svc.update_tower(
        db, ctx.user, tower, code=body.code, name=body.name, area_id=body.area_id
    )
    return _tower_out(tower, svc.in_use(db, "tower", tower.id))


# --- plans --------------------------------------------------------------------------------------


@router.get("/plans")
def list_plans(_: AuthContext = Depends(_can), db: Session = Depends(get_db)) -> dict:
    return {"items": [_plan_out(p, used) for p, used in svc.list_plans(db)]}


@router.post("/plans", response_model=PlanOut, status_code=201)
def create_plan(
    body: PlanCreate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> PlanOut:
    plan = svc.create_plan(db, ctx.user, body.name, body.trial_price, body.second_price)
    return _plan_out(plan, svc.in_use(db, "plan", plan.id))


@router.patch("/plans/{item_id}", response_model=PlanOut)
def update_plan(
    item_id: int, body: PlanUpdate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> PlanOut:
    plan = svc.get_item(db, "plan", item_id)
    plan = svc.update_plan(
        db,
        ctx.user,
        plan,
        name=body.name,
        trial_price=body.trial_price,
        second_price=body.second_price,
    )
    return _plan_out(plan, svc.in_use(db, "plan", plan.id))


# --- tiers and general (US3, US4) -------------------------------------------------------------


def _tiers_out(tiers: list[tuple[int, int]]) -> TiersOut:
    return TiersOut(items=[TierOut(min_count=c, rate=r) for c, r in tiers])


@router.get("/tiers", response_model=TiersOut)
def get_tiers(_: AuthContext = Depends(_can), db: Session = Depends(get_db)) -> TiersOut:
    return _tiers_out(svc.get_tiers(db))


@router.put("/tiers", response_model=TiersOut)
def replace_tiers(
    body: TiersBody, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> TiersOut:
    items = [(t.min_count, t.rate) for t in body.items]
    return _tiers_out(svc.replace_tiers(db, ctx.user, items))


@router.get("/general", response_model=GeneralOut)
def get_general(_: AuthContext = Depends(_can), db: Session = Depends(get_db)) -> GeneralOut:
    return GeneralOut(**svc.get_general(db))


@router.patch("/general", response_model=GeneralOut)
def update_general(
    body: GeneralUpdate, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> GeneralOut:
    return GeneralOut(**svc.update_general(db, ctx.user, body.changes()))


# --- shared: activate / deactivate / delete -----------------------------------------------------

_KINDS = {"areas": "area", "towers": "tower", "plans": "plan"}


def _out(db: Session, kind: str, item) -> AreaOut | TowerOut | PlanOut:
    if kind == "area":
        return _area_out(db, item)
    used = svc.in_use(db, kind, item.id)  # type: ignore[arg-type]
    return _tower_out(item, used) if kind == "tower" else _plan_out(item, used)


def _kind(collection: str) -> str:
    kind = _KINDS.get(collection)
    if kind is None:
        from app.errors import AppError

        raise AppError("not_found", 404)
    return kind


@router.post("/{collection}/{item_id}/deactivate")
def deactivate(
    collection: str, item_id: int, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
):
    kind = _kind(collection)
    item = svc.get_item(db, kind, item_id)  # type: ignore[arg-type]
    return _out(db, kind, svc.set_active(db, ctx.user, kind, item, False))  # type: ignore[arg-type]


@router.post("/{collection}/{item_id}/reactivate")
def reactivate(
    collection: str, item_id: int, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
):
    kind = _kind(collection)
    item = svc.get_item(db, kind, item_id)  # type: ignore[arg-type]
    return _out(db, kind, svc.set_active(db, ctx.user, kind, item, True))  # type: ignore[arg-type]


@router.delete("/{collection}/{item_id}", status_code=204)
def delete(
    collection: str, item_id: int, ctx: AuthContext = Depends(_can), db: Session = Depends(get_db)
) -> Response:
    kind = _kind(collection)
    item = svc.get_item(db, kind, item_id)  # type: ignore[arg-type]
    svc.delete_item(db, ctx.user, kind, item)  # type: ignore[arg-type]
    return Response(status_code=204)
