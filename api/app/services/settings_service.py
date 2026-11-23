"""Settings rules (specs/004 data-model.md, research.md R2/R5/R6, docs/system.md §10 v1.3).

- Every change writes one audit entry with old and new values; a no-op writes none.
- An item may be deleted only while unused. "Used" comes from a registry of reference checks
  (later features register theirs), backed by ON DELETE RESTRICT foreign keys in the database.
- Each public function that changes data commits its own transaction.
"""

import re
from collections.abc import Callable
from typing import Any, Literal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.phone import normalize_phone
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import AppSetting, Area, Plan, RewardTier, Tower, User
from app.models.catalog import MAX_AMOUNT
from app.services import audit_service

Kind = Literal["area", "tower", "plan"]
MODELS: dict[str, type[Area] | type[Tower] | type[Plan]] = {
    "area": Area,
    "tower": Tower,
    "plan": Plan,
}

NAME_MAX = 100
NAME_MESSAGE = "الاسم يجب أن يكون بين 1 و100 حرف"
CODE_RE = re.compile(r"^[A-Z0-9]{2,20}$")

# Unique indexes → the error the user sees.
_UNIQUE_ERRORS = {
    "areas_name_key": "name_taken",
    "plans_name_key": "name_taken",
    "towers_code_key": "code_taken",
}


# --- validation -----------------------------------------------------------------------------


def clean_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not 1 <= len(name) <= NAME_MAX:
        raise AppError("invalid_name", 422, message=NAME_MESSAGE)
    return name


def clean_code(raw: str) -> str:
    code = raw.strip().upper()
    if not CODE_RE.fullmatch(code):
        raise AppError("invalid_code", 422)
    return code


def check_amount(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_AMOUNT:
        raise AppError("invalid_amount", 422)
    return value


def _commit(db: Session) -> None:
    """Commit; a unique-index race that slipped past the pre-check becomes its friendly code."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        text = str(exc.orig)
        for constraint, code in _UNIQUE_ERRORS.items():
            if constraint in text:
                raise AppError(code, 409) from exc
        raise


def _name_taken(
    db: Session, model: type[Area] | type[Plan], name: str, except_id: int | None
) -> bool:
    query = select(model.id).where(func.lower(model.name) == name.lower())
    if except_id is not None:
        query = query.where(model.id != except_id)
    return db.execute(query).first() is not None


# --- usage registry (research.md R2) ------------------------------------------------------------

UsageCheck = Callable[[Session, int], int]
_USAGE_CHECKS: dict[str, list[UsageCheck]] = {"area": [], "tower": [], "plan": []}


def register_usage_check(kind: Kind, check: UsageCheck) -> None:
    """Later features register "is this item referenced?" checks (e.g. towers used by requests)."""
    _USAGE_CHECKS[kind].append(check)


def unregister_usage_check(kind: Kind, check: UsageCheck) -> None:
    _USAGE_CHECKS[kind].remove(check)


def usage_count(db: Session, kind: Kind, item_id: int) -> int:
    return sum(check(db, item_id) for check in _USAGE_CHECKS[kind])


def in_use(db: Session, kind: Kind, item_id: int) -> bool:
    return usage_count(db, kind, item_id) > 0


def _area_tower_count(db: Session, area_id: int) -> int:
    return db.execute(
        select(func.count()).select_from(Tower).where(Tower.area_id == area_id)
    ).scalar_one()


register_usage_check("area", _area_tower_count)


# --- generic helpers ----------------------------------------------------------------------------


def snapshot(kind: Kind, item: Any) -> dict[str, Any]:
    """The audited, human-meaningful fields of an item."""
    if kind == "area":
        return {"name": item.name, "is_active": item.is_active}
    if kind == "tower":
        return {
            "code": item.code,
            "name": item.name,
            "area": item.area.name,
            "is_active": item.is_active,
        }
    return {
        "name": item.name,
        "trial_price": item.trial_price,
        "second_price": item.second_price,
        "is_active": item.is_active,
    }


def _audit(
    db: Session,
    actor: User,
    kind: Kind,
    action: str,
    item_id: int,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    audit_service.record(
        db,
        actor_id=actor.id,
        action=f"{kind}.{action}",
        entity_type=kind,
        entity_id=item_id,
        before=before,
        after=after,
    )


def get_item(db: Session, kind: Kind, item_id: int) -> Any:
    item = db.get(MODELS[kind], item_id)
    if item is None:
        raise AppError("not_found", 404)
    return item


def set_active(db: Session, actor: User, kind: Kind, item: Any, active: bool) -> Any:
    if item.is_active == active:
        return item  # no-op
    item.is_active = active
    item.updated_at = utc_now()
    _audit(
        db,
        actor,
        kind,
        "reactivated" if active else "deactivated",
        item.id,
        {"is_active": not active},
        {"is_active": active},
    )
    _commit(db)
    return item


def delete_item(db: Session, actor: User, kind: Kind, item: Any) -> None:
    """Delete an unused item; a used one (registry or FK) is refused with item_in_use."""
    if in_use(db, kind, item.id):
        raise AppError("item_in_use", 409)
    before = snapshot(kind, item)
    item_id = item.id
    try:
        with db.begin_nested():
            db.delete(item)
            db.flush()
    except IntegrityError as exc:  # a reference no check knew about: the FK backstop
        raise AppError("item_in_use", 409) from exc
    _audit(db, actor, kind, "deleted", item_id, before, None)
    _commit(db)


def _apply_changes(
    db: Session, actor: User, kind: Kind, item: Any, changes: dict[str, tuple[Any, Any]]
) -> Any:
    """`changes` maps audited field → (old, new); the caller already set the new values."""
    if not changes:
        return item
    item.updated_at = utc_now()
    _audit(
        db,
        actor,
        kind,
        "updated",
        item.id,
        {k: old for k, (old, _) in changes.items()},
        {k: new for k, (_, new) in changes.items()},
    )
    _commit(db)
    db.refresh(item)
    return item


# --- areas --------------------------------------------------------------------------------------


def list_areas(db: Session) -> list[tuple[Area, int, bool]]:
    areas = db.execute(select(Area).order_by(Area.is_active.desc(), Area.name)).scalars()
    return [(a, _area_tower_count(db, a.id), in_use(db, "area", a.id)) for a in areas]


def create_area(db: Session, actor: User, name: str) -> Area:
    name = clean_name(name)
    if _name_taken(db, Area, name, None):
        raise AppError("name_taken", 409)
    area = Area(name=name, is_active=True)
    db.add(area)
    db.flush()
    _audit(db, actor, "area", "created", area.id, None, snapshot("area", area))
    _commit(db)
    return area


def update_area(db: Session, actor: User, area: Area, name: str | None) -> Area:
    changes: dict[str, tuple[Any, Any]] = {}
    if name is not None:
        new = clean_name(name)
        if new != area.name:
            if _name_taken(db, Area, new, area.id):
                raise AppError("name_taken", 409)
            changes["name"] = (area.name, new)
            area.name = new
    return _apply_changes(db, actor, "area", area, changes)


# --- towers -------------------------------------------------------------------------------------


def list_towers(db: Session) -> list[tuple[Tower, bool]]:
    towers = db.execute(select(Tower).order_by(Tower.is_active.desc(), Tower.code)).scalars()
    return [(t, in_use(db, "tower", t.id)) for t in towers]


def _area_or_422(db: Session, area_id: int) -> Area:
    area = db.get(Area, area_id)
    if area is None:
        raise AppError("validation_error", 422)
    return area


def _code_taken(db: Session, code: str, except_id: int | None) -> bool:
    query = select(Tower.id).where(Tower.code == code)
    if except_id is not None:
        query = query.where(Tower.id != except_id)
    return db.execute(query).first() is not None


def create_tower(db: Session, actor: User, code: str, name: str, area_id: int) -> Tower:
    code = clean_code(code)
    name = clean_name(name)
    area = _area_or_422(db, area_id)
    if not area.is_active:
        raise AppError("area_inactive", 422)  # new towers need an active area (FR-004)
    if _code_taken(db, code, None):
        raise AppError("code_taken", 409)
    tower = Tower(code=code, name=name, area_id=area.id, is_active=True)
    db.add(tower)
    db.flush()
    db.refresh(tower)
    _audit(db, actor, "tower", "created", tower.id, None, snapshot("tower", tower))
    _commit(db)
    return tower


def update_tower(
    db: Session,
    actor: User,
    tower: Tower,
    *,
    code: str | None = None,
    name: str | None = None,
    area_id: int | None = None,
) -> Tower:
    changes: dict[str, tuple[Any, Any]] = {}
    if code is not None:
        new_code = clean_code(code)
        if new_code != tower.code:
            if in_use(db, "tower", tower.id):
                raise AppError("code_locked", 409)  # usernames already use it (§10 v1.3)
            if _code_taken(db, new_code, tower.id):
                raise AppError("code_taken", 409)
            changes["code"] = (tower.code, new_code)
            tower.code = new_code
    if name is not None:
        new_name = clean_name(name)
        if new_name != tower.name:
            changes["name"] = (tower.name, new_name)
            tower.name = new_name
    if area_id is not None and area_id != tower.area_id:
        # Editing may keep or pick any existing area, even an inactive one (spec edge case).
        area = _area_or_422(db, area_id)
        changes["area"] = (tower.area.name, area.name)
        tower.area_id = area.id
        tower.area = area
    return _apply_changes(db, actor, "tower", tower, changes)


# --- plans --------------------------------------------------------------------------------------


def list_plans(db: Session) -> list[tuple[Plan, bool]]:
    plans = db.execute(select(Plan).order_by(Plan.is_active.desc(), Plan.name)).scalars()
    return [(p, in_use(db, "plan", p.id)) for p in plans]


def create_plan(db: Session, actor: User, name: str, trial_price: int, second_price: int) -> Plan:
    name = clean_name(name)
    check_amount(trial_price)
    check_amount(second_price)
    if _name_taken(db, Plan, name, None):
        raise AppError("name_taken", 409)
    plan = Plan(name=name, trial_price=trial_price, second_price=second_price, is_active=True)
    db.add(plan)
    db.flush()
    _audit(db, actor, "plan", "created", plan.id, None, snapshot("plan", plan))
    _commit(db)
    return plan


def update_plan(
    db: Session,
    actor: User,
    plan: Plan,
    *,
    name: str | None = None,
    trial_price: int | None = None,
    second_price: int | None = None,
) -> Plan:
    """Price changes apply to new requests only: requests copy prices at submit (FR-006)."""
    changes: dict[str, tuple[Any, Any]] = {}
    if name is not None:
        new_name = clean_name(name)
        if new_name != plan.name:
            if _name_taken(db, Plan, new_name, plan.id):
                raise AppError("name_taken", 409)
            changes["name"] = (plan.name, new_name)
            plan.name = new_name
    for field, value in (("trial_price", trial_price), ("second_price", second_price)):
        if value is not None:
            check_amount(value)
            if value != getattr(plan, field):
                changes[field] = (getattr(plan, field), value)
                setattr(plan, field, value)
    return _apply_changes(db, actor, "plan", plan, changes)


# --- catalog (FR-014) ---------------------------------------------------------------------------


def catalog(db: Session) -> tuple[list[Area], list[Tower], list[Plan]]:
    """What the new-request form may offer: active items, and no towers of inactive areas."""
    areas = list(
        db.execute(select(Area).where(Area.is_active.is_(True)).order_by(Area.name)).scalars()
    )
    towers = list(
        db.execute(
            select(Tower)
            .join(Area, Area.id == Tower.area_id)
            .where(Tower.is_active.is_(True), Area.is_active.is_(True))
            .order_by(Tower.code)
        )
        .unique()
        .scalars()
    )
    plans = list(
        db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.name)).scalars()
    )
    return areas, towers, plans


# --- reward tiers (US3, data-model.md › reward_tiers) ---------------------------------------

MAX_TIERS = 20
MAX_TIER_COUNT = 10_000


def _tiers_error(message: str) -> AppError:
    return AppError("invalid_tiers", 422, message=message)


def validate_tiers(items: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """(min_count, rate) pairs in any order; returns them ascending. Raises invalid_tiers."""
    if not items:
        raise _tiers_error("أضف شريحة واحدة على الأقل")
    if len(items) > MAX_TIERS:
        raise _tiers_error("الحد الأقصى 20 شريحة")
    for count, rate in items:
        if not 0 <= count <= MAX_TIER_COUNT:
            raise _tiers_error("أقل عدد يجب أن يكون من 0 إلى 10,000")
        if not 1 <= rate <= MAX_AMOUNT:
            raise _tiers_error("سعر المشترك يجب أن يكون من 1 إلى 10,000,000")
    ordered = sorted(items, key=lambda t: t[0])
    if ordered[0][0] != 0:
        raise _tiers_error("الشريحة الأولى يجب أن تبدأ من 0")
    counts = [c for c, _ in ordered]
    if len(set(counts)) != len(counts):
        raise _tiers_error("أقل عدد يجب أن يكون تصاعدياً بلا تكرار")
    return ordered


def get_tiers(db: Session) -> list[tuple[int, int]]:
    rows = db.execute(select(RewardTier).order_by(RewardTier.min_count)).scalars()
    return [(t.min_count, t.rate) for t in rows]


def _tiers_json(tiers: list[tuple[int, int]]) -> list[dict[str, int]]:
    return [{"min_count": c, "rate": r} for c, r in tiers]


def replace_tiers(db: Session, actor: User, items: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Replace the whole list in one transaction. Applies to every unpaid month (§9 v1.3)."""
    new = validate_tiers(items)
    old = get_tiers(db)
    if new == old:
        return old  # no-op
    db.execute(delete(RewardTier))
    db.flush()
    db.add_all([RewardTier(min_count=c, rate=r) for c, r in new])
    audit_service.record(
        db,
        actor_id=actor.id,
        action="reward_tiers.updated",
        entity_type="reward_tiers",
        entity_id="list",
        before={"tiers": _tiers_json(old)},
        after={"tiers": _tiers_json(new)},
    )
    _commit(db)
    return new


# --- general settings (US4, data-model.md › app_settings) -----------------------------------

OTP_MINUTES_KEY = "otp_validity_minutes"
OTP_MINUTES_MIN, OTP_MINUTES_MAX = 5, 1440
# «رقم واتساب الإدارة» for «الاتصال بالإدارة»
# (specs/009 data-model.md › app_settings.admin_whatsapp).
ADMIN_WHATSAPP_KEY = "admin_whatsapp"
_GENERAL_DEFAULTS: dict[str, Any] = {OTP_MINUTES_KEY: 60, ADMIN_WHATSAPP_KEY: None}


def get_general(db: Session) -> dict[str, Any]:
    values = dict(_GENERAL_DEFAULTS)
    for row in db.execute(select(AppSetting).where(AppSetting.key.in_(values))).scalars():
        values[row.key] = row.value
    return values


def admin_whatsapp(db: Session) -> str | None:
    return get_general(db)[ADMIN_WHATSAPP_KEY]


def _clean_general(key: str, value: Any) -> Any:
    if key == OTP_MINUTES_KEY:
        if not OTP_MINUTES_MIN <= value <= OTP_MINUTES_MAX:
            raise AppError("invalid_otp_minutes", 422)
        return value
    # admin_whatsapp: empty clears; otherwise §8.1 or `invalid_phone`.
    if value is None or not str(value).strip():
        return None
    phone = normalize_phone(value)
    if phone is None:
        raise AppError("invalid_phone", 422)
    return phone


def update_general(db: Session, actor: User, changes: dict[str, Any]) -> dict[str, Any]:
    """Change only the keys given; one audit row per key whose value really changes."""
    cleaned = {key: _clean_general(key, value) for key, value in changes.items()}
    current = get_general(db)
    for key, new in cleaned.items():
        old = current[key]
        if old == new:
            continue  # no-op
        row = db.get(AppSetting, key)
        if new is None:
            if row is not None:
                db.delete(row)
        else:
            if row is None:
                row = AppSetting(key=key, value=new)
                db.add(row)
            row.value = new
            row.updated_by = actor.id
            row.updated_at = utc_now()
        audit_service.record(
            db,
            actor_id=actor.id,
            action="app_setting.updated",
            entity_type="app_setting",
            entity_id=key,
            before={key: old},
            after={key: new},
        )
    _commit(db)
    return get_general(db)
