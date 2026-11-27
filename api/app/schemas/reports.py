"""«التقارير والتصدير» schemas (specs/019 contracts/api.md).

Allow-lists: a report row never carries a national ID, family number, card field, image, phone,
username or address, and nothing here carries an amount, rate or payment (FR-002, FR-016;
research R9, R12).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.report_period import PeriodKind

DateKind = Literal["submitted", "linked"]
ReportStatus = Literal["pending_review", "approved", "rejected", "linked"]
RequestType = Literal["new", "additional", "return"]


class ReportFilters(BaseModel):
    """The shared filters of the report and the export (query parameters)."""

    model_config = ConfigDict(populate_by_name=True)

    period: PeriodKind
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
    date_kind: DateKind = "submitted"
    area_id: int | None = Field(default=None, ge=1)
    tower_id: int | None = Field(default=None, ge=1)
    marketer_id: int | None = Field(default=None, ge=1)
    plan_id: int | None = Field(default=None, ge=1)
    status: ReportStatus | None = None
    type: RequestType | None = None


class ReportRow(BaseModel):
    id: int
    number: int
    number_label: str
    # Null for a deleted request (§7.4): only its kept fields are shown.
    name: str | None
    deleted: bool
    tower: str
    plan: str
    marketer: str
    status: ReportStatus
    type: RequestType
    submitted_at: datetime
    linked_at: datetime | None


class StatusCount(BaseModel):
    status: ReportStatus
    count: int


class TowerCount(BaseModel):
    tower_id: int
    tower: str
    count: int


class MarketerCount(BaseModel):
    marketer_id: int
    marketer: str
    count: int


class ReportSummary(BaseModel):
    by_status: list[StatusCount]
    by_tower: list[TowerCount]
    by_marketer: list[MarketerCount]


class ReportOut(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[ReportRow]
    summary: ReportSummary
    can_export_identity: bool


class AreaOption(BaseModel):
    id: int
    name: str
    active: bool


class TowerOption(BaseModel):
    id: int
    code: str
    name: str
    area_id: int
    active: bool


class PlanOption(BaseModel):
    id: int
    name: str
    active: bool


class MarketerOption(BaseModel):
    id: int
    name: str
    archived: bool
    active: bool


class ReportOptions(BaseModel):
    areas: list[AreaOption]
    towers: list[TowerOption]
    plans: list[PlanOption]
    marketers: list[MarketerOption]
