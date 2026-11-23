"""Admin review bodies and responses (specs/010 contracts/api.md).

Only the main admin and admins with `review` receive these (FR-001, FR-004). `card_readings` (the
raw reader answers) is never part of any of them (Principle II).
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool

from app.schemas.requests import ReasonCode, RequestStatus, RequestType

ReasonState = Literal["open", "resolved", "not_applicable"]
ReturnBasis = Literal["identity", "phone"]
ReviewWarning = Literal["same_person", "id_conflict", "return_target_lost"]
RejectionReason = Literal[
    "card_unclear", "numbers_mismatch", "under_15_days", "active_subscription", "other"
]
PinField = Literal["national_id", "family_number"]
PinSource = Literal["reading", "mrz", "marketer", "typed"]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- list ---


class PendingItem(BaseModel):
    id: int
    number_label: str
    type: RequestType
    reasons: list[ReasonCode]
    marketer_name: str
    full_name: str
    tower_code: str
    tower_name: str
    submitted_at: datetime


class PendingList(BaseModel):
    total: int
    items: list[PendingItem]


# --- the request file ---


class LinkedRecordOut(BaseModel):
    source: str
    ref: str
    available: bool
    full_name: str | None = None
    username: str | None = None
    phone: str | None = None
    tower_code: str | None = None
    tower_name: str | None = None
    registered_at: datetime | None = None
    status: str | None = None
    image_ids: list[uuid.UUID] = []
    expiry: date | None = None


class ReasonOut(BaseModel):
    reason: ReasonCode
    state: ReasonState
    added_at_review: bool
    basis: ReturnBasis | None = None
    fields: list[PinField] = []
    record: LinkedRecordOut | None = None


class PinOut(BaseModel):
    value: str
    source: PinSource
    by: str
    at: datetime


class NumberOut(BaseModel):
    reading: str | None
    mrz: str | None = None  # national ID only
    marketer: str
    current: str
    edited: bool
    pins: list[PinOut]


class NumbersOut(BaseModel):
    national_id: NumberOut
    family_number: NumberOut


class ImageOut(BaseModel):
    id: uuid.UUID
    side: Literal["front", "back"]


class LocationOut(BaseModel):
    lat: float
    lng: float
    source: str
    accuracy_m: int | None


class DecisionOut(BaseModel):
    status: Literal["approved", "rejected"]
    by: str | None  # null: the automatic approval of §6.1 row 5
    at: datetime
    counts_commission: bool | None = None
    despite_warnings: list[ReviewWarning] = []
    reason: RejectionReason | None = None
    label: str | None = None


class RequestFileOut(BaseModel):
    id: int
    number_label: str
    type: RequestType
    status: RequestStatus
    names: dict[str, str | None]
    names_reading: dict[str, str | None]
    full_name: str
    national_id: str
    family_number: str
    birth_date: date
    issue_date: date
    expiry_date: date
    birth_place: str
    issuing_authority: str
    images: list[ImageOut]
    location: LocationOut
    address: str
    landmark: str
    area_name: str
    tower_code: str
    tower_name: str
    plan_name: str
    trial_price: int
    second_price: int
    phone: str
    otp_verified_at: datetime
    username: str
    marketer_name: str
    submitted_at: datetime
    numbers: NumbersOut
    reasons: list[ReasonOut]
    warnings: list[ReviewWarning]
    decision: DecisionOut | None


# --- actions ---


class AcceptIn(_Body):
    counts_commission: StrictBool | None = None
    confirm_warnings: list[ReviewWarning] = []


class RejectIn(_Body):
    reason: RejectionReason
    note: str | None = None


class PinIn(_Body):
    field: PinField
    source: PinSource
    value: str | None = None


# --- admin home ---


class HomeCounts(BaseModel):
    submitted: int
    approved: int
    pending: int
    linked: int
    rejected: int


class HomeOut(BaseModel):
    today: HomeCounts
    month: HomeCounts
