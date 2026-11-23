"""Submitted requests (specs/008 contracts/api.md).

Never carries the card readings, the national ID, the family number or who matched (Principle II,
FR-007). `username` is shown only once the request is approved or linked (research R7).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

RequestStatus = Literal["pending_review", "approved", "rejected", "linked"]
RequestType = Literal["new", "additional", "return"]
ReasonCode = Literal["family_exists", "numbers_edited", "return"]
# The page's text: «تمت الموافقة» / «بانتظار موافقة المسؤول» / «طلبك بانتظار التدقيق».
ResultCode = Literal["approved", "pending_family", "pending_review", "rejected", "linked"]


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
    area_name: str
    plan_name: str
    trial_price: int
    second_price: int
    phone: str
    username: str | None
    submitted_at: datetime
    approved_at: datetime | None
    result: ResultCode


class RequestListItem(BaseModel):
    id: int
    number_label: str
    full_name: str
    status: RequestStatus
    type: RequestType
    submitted_at: datetime


class RequestList(BaseModel):
    items: list[RequestListItem]
