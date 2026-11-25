"""SAS import bodies (specs/015 contracts/api.md). Only `reports` admins and the main admin receive
them. Flagged rows carry the values the admin decides on; nothing here ever holds a password."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Choice = Literal["import", "skip"]
Kind = Literal["new", "update", "unchanged"]


class SasPreviewCounts(BaseModel):
    rows: int
    new: int
    update: int
    unchanged: int
    missing_from_file: int
    flagged: int
    waiting_choice: int
    same_username_in_sijil: int
    no_valid_phone: int
    username_no_phone: int
    date_unreadable: int
    phone_dup_file: int
    phone_in_legacy: int


class SasPrefix(BaseModel):
    prefix: str
    rows: int
    tower_id: int | None
    from_previous: bool
    chosen: bool


class SasTower(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool


class SasFlaggedRow(BaseModel):
    index: int
    sas_id: str | None
    username: str | None
    full_name: str
    phone: str | None
    username_phone: str | None
    kind: Kind
    # {"code": ..., plus "rows" | "requests"} (research R9)
    flags: list[dict[str, Any]]
    allowed: list[Choice]
    choice: Choice | None


class SasPreview(BaseModel):
    id: uuid.UUID
    file_name: str
    expires_at: datetime
    counts: SasPreviewCounts
    prefixes: list[SasPrefix]
    waiting_prefixes: int
    towers: list[SasTower]
    flagged: list[SasFlaggedRow]


class SasChoiceIn(BaseModel):
    index: int
    choice: Choice


class SasPrefixIn(BaseModel):
    prefix: str = Field(min_length=1, max_length=100)
    # None = «بلا برج».
    tower_id: int | None


class SasChoicesIn(BaseModel):
    choices: list[SasChoiceIn] = Field(default_factory=list, max_length=50_000)
    prefixes: list[SasPrefixIn] = Field(default_factory=list, max_length=5_000)


class SasSkippedRow(BaseModel):
    index: int
    sas_id: str | None


class SasImportSummary(BaseModel):
    """No usernames, phones or names (FR-010)."""

    import_id: int
    rows: int
    added: int
    updated: int
    unchanged: int
    skipped: int
    missing_marked: int
    missing_cleared: int
    without_phone: int
    prefixes_mapped: int
    skipped_rows: list[SasSkippedRow]
