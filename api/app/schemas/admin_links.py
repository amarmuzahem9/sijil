"""«بانتظار الربط» rows and actions (specs/013 contracts/api.md).

`LinkRow` is an allow-list: the fields an admin needs to find the subscriber in SAS, and nothing
from the card (no identity number, card field or image; constitution Principle II, FR-002).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt

UnlinkReason = Literal["not_linked_in_sas", "by_mistake", "other_request_linked", "other"]


class LinkRow(BaseModel):
    id: int
    number_label: str
    full_name: str | None
    username: str | None
    phone: str | None
    tower_name: str
    tower_code: str
    plan_name: str
    # The marketer's current name, like the link message (specs/012).
    marketer_name: str
    approved_at: datetime | None
    # The current link: null while waiting.
    linked_at: datetime | None = None
    linked_by_name: str | None = None
    link_id: int | None = None


class LinkList(BaseModel):
    items: list[LinkRow]
    total: int


class UnlinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: UnlinkReason
    # The current link the page showed; a newer link makes the undo stale (research R2).
    link_id: StrictInt
