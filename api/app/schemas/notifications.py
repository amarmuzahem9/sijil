"""Marketer notifications (specs/012 contracts/api.md).

`full_name` is read from the request at display time; it is null once the request is deleted (011).
`reason_label` is the fixed label of the reason code, never the reviewer's note.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NotificationKind = Literal["approved", "rejected", "linked", "unlinked", "deleted"]


class NotificationOut(BaseModel):
    id: int
    kind: NotificationKind
    request_id: int
    number_label: str
    full_name: str | None
    deleted: bool
    reason_label: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next_before: int | None


class UnreadCount(BaseModel):
    count: int
