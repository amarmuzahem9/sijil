"""Settings bodies and items (specs/004 contracts/api.md).

Bodies are strict: unknown fields are refused, money and counts are integers only (a string such
as "20,000" is refused; the web parses Arabic digits before sending). Length and range rules live
in settings_service so each failure returns its own code.
"""

from pydantic import BaseModel, ConfigDict, StrictInt


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- areas -----------------------------------------------------------------------------------


class AreaCreate(_Body):
    name: str


class AreaUpdate(_Body):
    name: str | None = None


class AreaOut(BaseModel):
    id: int
    name: str
    is_active: bool
    in_use: bool
    tower_count: int


# --- towers ----------------------------------------------------------------------------------


class TowerCreate(_Body):
    code: str
    name: str
    area_id: StrictInt


class TowerUpdate(_Body):
    code: str | None = None
    name: str | None = None
    area_id: StrictInt | None = None


class AreaRef(BaseModel):
    id: int
    name: str
    is_active: bool


class TowerOut(BaseModel):
    id: int
    code: str
    name: str
    area: AreaRef
    is_active: bool
    in_use: bool


# --- plans -----------------------------------------------------------------------------------


class PlanCreate(_Body):
    name: str
    trial_price: StrictInt
    second_price: StrictInt


class PlanUpdate(_Body):
    name: str | None = None
    trial_price: StrictInt | None = None
    second_price: StrictInt | None = None


class PlanOut(BaseModel):
    id: int
    name: str
    trial_price: int
    second_price: int
    is_active: bool
    in_use: bool


class ItemList(BaseModel):
    items: list[AreaOut] | list[TowerOut] | list[PlanOut]


# --- catalog (FR-014) ------------------------------------------------------------------------


class CatalogArea(BaseModel):
    id: int
    name: str


class CatalogTower(BaseModel):
    id: int
    code: str
    name: str
    area_id: int


class CatalogPlan(BaseModel):
    id: int
    name: str
    trial_price: int
    second_price: int


class Catalog(BaseModel):
    areas: list[CatalogArea]
    towers: list[CatalogTower]
    plans: list[CatalogPlan]


# --- tiers and general (US3, US4) --------------------------------------------------------------


class TierIn(_Body):
    min_count: StrictInt
    rate: StrictInt


class TiersBody(_Body):
    items: list[TierIn]


class TierOut(BaseModel):
    min_count: int
    rate: int


class TiersOut(BaseModel):
    items: list[TierOut]


class GeneralUpdate(_Body):
    otp_validity_minutes: StrictInt


class GeneralOut(BaseModel):
    otp_validity_minutes: int
