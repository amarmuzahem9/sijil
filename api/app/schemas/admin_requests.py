"""Admin review bodies and responses (specs/010 contracts/api.md).

Only the main admin and admins with `review` receive these (FR-001, FR-004). `card_readings` (the
raw reader answers) is never part of any of them (Principle II).
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.schemas.requests import ReasonCode, RequestStatus, RequestType

ReasonState = Literal["open", "resolved", "not_applicable"]
ReturnBasis = Literal["identity", "phone"]
ReviewWarning = Literal["same_person", "id_conflict", "return_target_lost"]
RejectionReason = Literal[
    "card_unclear", "numbers_mismatch", "under_15_days", "active_subscription", "other"
]
PinField = Literal["national_id", "family_number"]
PinSource = Literal["reading", "mrz", "marketer", "typed"]
# specs/011 data-model.md › Deletion reasons
DeletionReason = Literal["duplicate", "test", "entry_error", "other"]


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
    # specs/011 R10: a deleted Sijil request, shown as «سجل محذوف (#T3C-…)».
    deleted: bool = False
    number_label: str | None = None
    # specs/014 R12: only on a legacy subscriber. No family number on any record.
    legacy_number: str | None = None
    incomplete: bool | None = None
    extra: dict[str, str | None] | None = None
    # specs/015 R13: only on a SAS subscriber. Never notes or parent_name.
    expiry_as_of: date | None = None
    last_online: datetime | None = None
    group_name: str | None = None
    username_phone: str | None = None
    missing_from_file: date | None = None


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


class DeletedOut(BaseModel):
    """The deletion mark (specs/011 contracts/api.md)."""

    at: datetime
    by_name: str
    reason: DeletionReason


class RequestFileOut(BaseModel):
    """A deleted request (`deleted` set) carries only the kept fields: every personal field is
    null, and names, images, numbers, linked records and warnings are empty (specs/011 R9)."""

    id: int
    number_label: str
    type: RequestType
    status: RequestStatus
    names: dict[str, str | None]
    names_reading: dict[str, str | None]
    full_name: str | None
    national_id: str | None
    family_number: str | None
    birth_date: date | None
    issue_date: date | None
    expiry_date: date | None
    birth_place: str | None
    issuing_authority: str | None
    images: list[ImageOut]
    location: LocationOut | None
    address: str | None
    landmark: str | None
    area_name: str
    tower_code: str
    tower_name: str
    plan_name: str
    trial_price: int
    second_price: int
    phone: str | None
    otp_verified_at: datetime
    username: str | None
    marketer_name: str
    submitted_at: datetime
    numbers: NumbersOut | None
    reasons: list[ReasonOut]
    warnings: list[ReviewWarning]
    decision: DecisionOut | None
    deleted: DeletedOut | None = None
    # «حذف» is offered: the caller holds `delete`, and the request is pending or rejected.
    can_delete: bool = False


# --- actions ---


class AcceptIn(_Body):
    counts_commission: StrictBool | None = None
    confirm_warnings: list[ReviewWarning] = []


class RejectIn(_Body):
    reason: RejectionReason
    note: str | None = None


class ByNumberOut(BaseModel):
    """«فتح طلب برقمه» (specs/011 R8): the id of the file to open."""

    id: int


class DeleteIn(_Body):
    """«حذف»: a reason from the list and the request number typed back (specs/011 R6)."""

    reason: DeletionReason
    confirm_number: str = Field(max_length=40)


class PinIn(_Body):
    """`value` only with `typed` (the server reads the other sources itself); `mrz` only for the
    national ID (research R4)."""

    field: PinField
    source: PinSource
    value: str | None = None

    @model_validator(mode="after")
    def _source_rules(self) -> "PinIn":
        if (self.source == "typed") != (self.value is not None):
            raise ValueError("value goes with source typed only")
        if self.source == "mrz" and self.field != "national_id":
            raise ValueError("mrz is for the national ID only")
        return self


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
    # Main admin only; [] for other admins (specs/016 FR-017).
    backup_warnings: list[str] = []
    # Undos after payment in the last 30 days; main admin and `commissions` only, null for other
    # admins (specs/017 FR-015).
    commission_alerts: int | None = None
