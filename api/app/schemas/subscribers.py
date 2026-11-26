"""«المشتركون» schemas (specs/018 contracts/api.md). Allow-lists: a result row never carries a
national ID, family number, card field or image (research R7)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Source = Literal["sijil", "legacy", "sas"]


class ResultRow(BaseModel):
    source: Source
    ref: str
    number_label: str | None
    legacy_number: str | None
    full_name: str | None
    tower_name: str | None
    tower_code: str | None
    phone: str | None
    # Request status, legacy status text, or the SAS expiry date «حسب آخر استيراد».
    status: str | None
    registered_at: datetime | None
    # A deleted request found by its number: every other field is null (§7.4).
    deleted: bool


class SearchOut(BaseModel):
    kind: str
    items: list[ResultRow]
    total: int
