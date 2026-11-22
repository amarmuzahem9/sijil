"""Draft bodies and responses (specs/005 contracts/api.md).

`DraftChanges` is a partial update: an omitted key is unchanged and `null` clears the field
(`model_fields_set` tells the two apart). Prices and catalog copies are never accepted from the
client; the server fills them (research.md R4). Length rules live in draft_service so a failure
returns `too_long` with the field name.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationIn(_Body):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    # gps: the phone; map: tap or drag; coords: typed or pasted; search: a Places result.
    source: Literal["gps", "map", "coords", "search"]
    accuracy_m: StrictInt | None = Field(default=None, ge=0)


class DraftChanges(_Body):
    first_name: str | None = None
    father_name: str | None = None
    grandfather_name: str | None = None
    great_grandfather_name: str | None = None
    surname: str | None = None
    mother_first_name: str | None = None
    mother_second_name: str | None = None
    mother_third_name: str | None = None
    mother_surname: str | None = None
    national_id: str | None = None
    family_number: str | None = None
    location: LocationIn | None = None
    address: str | None = None
    landmark: str | None = None
    area_id: StrictInt | None = None
    tower_id: StrictInt | None = None
    plan_id: StrictInt | None = None
    phone_input: str | None = None
    # Feature 006 (contracts/api.md): «لا يوجد لقب على البطاقة», and confirming a national ID
    # that differs from the verified MRZ. Provenance and readings are never accepted.
    no_surname: bool | None = None
    national_id_confirmed: bool | None = None
    # Back of the card (owner change, system.md v1.8): ISO dates and text.
    birth_date: date | None = None
    birth_place: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    issuing_authority: str | None = None


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


class CardFieldMarkOut(BaseModel):
    """Provenance of one card field (specs/006 data-model.md › drafts.card_fields)."""

    source: Literal["card", "edited"]
    original: str | None = None
    confidence: float | None = None
    from_: Literal["front", "back", "mrz"] | None = Field(default=None, alias="from")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class NationalIdCheckOut(BaseModel):
    mrz: str
    mismatch: bool
    confirmed: bool


class CardReadingSideOut(BaseModel):
    state: Literal["pending", "running", "done", "reshoot", "failed"]
    reason: str | None = None
    finished_at: datetime | None = None
    # Front only: the card's surname line is empty (FR-017 hint).
    surname_empty: bool | None = None


class CardReadingOut(BaseModel):
    front: CardReadingSideOut | None = None
    back: CardReadingSideOut | None = None


class CardReadingStatusOut(CardReadingOut):
    """GET /api/drafts/{id}/card-reading (the 2-second poll while a reading runs)."""

    version: int
    same_client: bool


class DraftOut(BaseModel):
    id: uuid.UUID
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    first_name: str | None
    father_name: str | None
    grandfather_name: str | None
    great_grandfather_name: str | None
    surname: str | None
    mother_first_name: str | None
    mother_second_name: str | None
    mother_third_name: str | None
    mother_surname: str | None
    full_name: str | None
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
    birth_date: date | None = None
    birth_place: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    issuing_authority: str | None = None
    images: DraftImages
    no_surname: bool = False
    card_fields: dict[str, CardFieldMarkOut] = Field(default_factory=dict)
    national_id_check: NationalIdCheckOut | None = None
    card_reading: CardReadingOut = Field(default_factory=CardReadingOut)
    missing: list[MissingOut]
    notices: list[NoticeOut] = Field(default_factory=list)


class DraftListItem(BaseModel):
    id: uuid.UUID
    full_name: str | None
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
