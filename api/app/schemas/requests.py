"""Submitted requests (specs/008 contracts/api.md).

Never carries the card readings, the national ID, the family number or who matched (Principle II,
FR-007). `username` is shown only once the request is approved or linked (research R7).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RequestStatus = Literal["pending_review", "approved", "rejected", "linked"]
RequestType = Literal["new", "additional", "return"]
ReasonCode = Literal["family_exists", "numbers_edited", "return", "numbers_conflict"]
# The page's text: «تمت الموافقة» / «بانتظار موافقة المسؤول» / «طلبك بانتظار التدقيق».
ResultCode = Literal[
    "approved", "pending_family", "pending_review", "pending_approval", "rejected", "linked"
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
    full_name: str
    tower_code: str
    tower_name: str
    area_name: str
    plan_name: str
    trial_price: int
    second_price: int
    phone: str
    # «نسخ التفاصيل» (system.md v1.11 §5.5).
    address: str
    landmark: str
    marketer_name: str
    username: str | None
    submitted_at: datetime
    approved_at: datetime | None
    result: ResultCode
    # The admin's rejection (specs/010 research R11): the code, and what the marketer reads (the
    # fixed label, or the admin's note for «سبب آخر»). No admin name, no linked record.
    rejection_reason: str | None = None
    rejection_label: str | None = None
    rejected_at: datetime | None = None


class RequestListItem(BaseModel):
    id: int
    number_label: str
    full_name: str
    status: RequestStatus
    type: RequestType
    submitted_at: datetime
    # «مرفوضة» rows show why (specs/010 FR-011).
    rejection_label: str | None = None


class RequestList(BaseModel):
    items: list[RequestListItem]
