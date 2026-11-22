"""Draft bodies and responses (specs/005 contracts/api.md).

`DraftChanges` is a partial update: an omitted key is unchanged and `null` clears the field
(`model_fields_set` tells the two apart). Prices and catalog copies are never accepted from the
client; the server fills them (research.md R4). Length rules live in draft_service so a failure
returns `too_long` with the field name.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationIn(_Body):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    source: Literal["gps", "map"]
    accuracy_m: StrictInt | None = Field(default=None, ge=0)


class DraftChanges(_Body):
    subscriber_name: str | None = None
    national_id: str | None = None
    family_number: str | None = None
    location: LocationIn | None = None
    address: str | None = None
    landmark: str | None = None
    area_id: StrictInt | None = None
    tower_id: StrictInt | None = None
    plan_id: StrictInt | None = None
    phone_input: str | None = None


class CreateBody(_Body):
    changes: DraftChanges = Field(default_factory=DraftChanges)


class PatchBody(_Body):
    version: StrictInt = Field(ge=1)
    changes: DraftChanges


# --- responses -------------------------------------------------------------------------------


class LocationOut(BaseModel):
    lat: float
    lng: float
    source: str | None
    accuracy_m: int | None


class ImageOut(BaseModel):
    id: uuid.UUID
    size_bytes: int
    width: int
    height: int
    created_at: datetime


class DraftImages(BaseModel):
    front: ImageOut | None = None
    back: ImageOut | None = None


class MissingOut(BaseModel):
    field: str
    code: str


class NoticeOut(BaseModel):
    field: str
    code: Literal["choice_unavailable", "price_changed"]
    old: dict[str, int] | None = None
    new: dict[str, int] | None = None


class DraftOut(BaseModel):
    id: uuid.UUID
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    subscriber_name: str | None
    national_id: str | None
    family_number: str | None
    location: LocationOut | None
    address: str | None
    landmark: str | None
    area_id: int | None
    tower_id: int | None
    plan_id: int | None
    area_name: str | None
    tower_code: str | None
    plan_name: str | None
    trial_price: int | None
    second_price: int | None
    phone_input: str | None
    phone_normalized: str | None
    images: DraftImages
    missing: list[MissingOut]
    notices: list[NoticeOut] = Field(default_factory=list)


class DraftListItem(BaseModel):
    id: uuid.UUID
    subscriber_name: str | None
    tower_code: str | None
    phone_normalized: str | None
    updated_at: datetime
    missing_count: int
    has_images: bool


class DraftList(BaseModel):
    items: list[DraftListItem]


class VersionOut(BaseModel):
    version: int
    updated_at: datetime
    same_client: bool
