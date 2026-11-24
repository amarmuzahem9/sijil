"""Submitted requests (specs/008 contracts/api.md).

Never carries the card readings, the national ID, the family number or who matched (Principle II,
FR-007). `username` is shown only once the request is approved or linked (research R7).

A deleted request (specs/011 R11) carries only its number, type, status, tower, submission time and
the deletion's time and reason; every other field is null, and `result` is `deleted`.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RequestStatus = Literal["pending_review", "approved", "rejected", "linked"]
RequestType = Literal["new", "additional", "return"]
ReasonCode = Literal["family_exists", "numbers_edited", "return", "numbers_conflict"]
# The page's text: «تمت الموافقة» / «بانتظار موافقة المسؤول» / «طلبك بانتظار التدقيق».
ResultCode = Literal[
    "approved",
    "pending_family",
    "pending_review",
    "pending_approval",
    "rejected",
    "linked",
    "deleted",
]


class SubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


class RequestOut(BaseModel):
    id: int
    number: int
    number_label: str
    type: RequestType
    status: RequestStatus
    reasons: list[ReasonCode]
    full_name: str | None
    tower_code: str
    tower_name: str
    area_name: str | None
    plan_name: str | None
    trial_price: int | None
    second_price: int | None
    phone: str | None
    # «نسخ التفاصيل» (system.md v1.11 §5.5).
    address: str | None
    landmark: str | None
    marketer_name: str | None
    username: str | None
    submitted_at: datetime
    approved_at: datetime | None
    result: ResultCode
    # The admin's rejection (specs/010 research R11): the code, and what the marketer reads (the
    # fixed label, or the admin's note for «سبب آخر»). No admin name, no linked record.
    rejection_reason: str | None = None
    rejection_label: str | None = None
    rejected_at: datetime | None = None
    # The current «تم الربط» (specs/013 R8); never who linked.
    linked_at: datetime | None = None
    # «محذوف» (specs/011 R11): when, and the reason's Arabic name. No admin name.
    deleted_at: datetime | None = None
    deletion_label: str | None = None
    # «رسالة الربط» (system.md v1.17 §8.4, specs/012 R1): accepted or linked only, else null.
    link_message: str | None = None


class RequestListItem(BaseModel):
    id: int
    number_label: str
    full_name: str | None
    status: RequestStatus
    type: RequestType
    submitted_at: datetime
    tower_code: str
    tower_name: str
    # «مرفوضة» rows show why (specs/010 FR-011).
    rejection_label: str | None = None
    # «محذوف» rows (specs/011 R11).
    deleted_at: datetime | None = None
    deletion_label: str | None = None
    # The current «تم الربط» (specs/013 R8).
    linked_at: datetime | None = None


class RequestList(BaseModel):
    items: list[RequestListItem]
