"""Legacy import bodies (specs/014 contracts/api.md). Only `reports` admins and the main admin
receive them; flagged rows carry the values the admin decides on."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

PreviewStatus = Literal["fetching", "ready", "failed"]
Choice = Literal["import", "skip", "correct"]


class StatusValue(BaseModel):
    value: str | None
    rows: int
    counts_in_check: bool


class PreviewCounts(BaseModel):
    rows: int
    ready: int
    flagged: int
    already_imported: int
    not_counted: int
    waiting_choice: int


class FlaggedRow(BaseModel):
    index: int
    legacy_number: str | None
    full_name: str
    phone_file: str | None
    phone: str | None
    family_number_file: str | None
    status_text: str | None
    counts_in_check: bool
    # {"code": ..., plus "rows" | "requests" | "side" and "outcome"} (research R6)
    flags: list[dict[str, Any]]
    allowed: list[Choice]
    choice: Choice | None
    corrected_family_number: str | None


class Preview(BaseModel):
    id: uuid.UUID
    status: PreviewStatus
    file_name: str
    expires_at: datetime
    images_total: int
    images_done: int
    counts: PreviewCounts
    status_values: list[StatusValue]
    flagged: list[FlaggedRow]
