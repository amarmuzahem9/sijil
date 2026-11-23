"""Settings bodies and items (specs/004 contracts/api.md).

Bodies are strict: unknown fields are refused, money and counts are integers only (a string such
as "20,000" is refused; the web parses Arabic digits before sending). Length and range rules live
in settings_service so each failure returns its own code.
"""

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator


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
    """Partial: only the keys sent change (specs/009 T030). At least one is required."""

    otp_validity_minutes: StrictInt | None = None
    admin_whatsapp: str | None = None

    @model_validator(mode="after")
    def _one_key(self) -> "GeneralUpdate":
        if not self.model_fields_set:
            raise ValueError("no setting given")
        if "otp_validity_minutes" in self.model_fields_set and self.otp_validity_minutes is None:
            raise ValueError("otp_validity_minutes cannot be null")
        return self

    def changes(self) -> dict:
        return {key: getattr(self, key) for key in self.model_fields_set}


class GeneralOut(BaseModel):
    otp_validity_minutes: int
    admin_whatsapp: str | None = None
