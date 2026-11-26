"""Commission schemas (specs/017 contracts/api.md). Allow-lists: no phone, username, identity
number, card field or image ever goes out (research R9)."""

from datetime import datetime

from pydantic import BaseModel, Field


class PastMonth(BaseModel):
    """One finished month for the marketer. Never who paid, when, or an alert (FR-007)."""

    month: str
    month_label: str
    count: int
    without_commission: int
    rate: int
    amount: int
    paid: bool


class PastMonths(BaseModel):
    items: list[PastMonth]


# --- the admin report (contracts/api.md) ---------------------------------------------------------


class MonthList(BaseModel):
    items: list[str]
    current: str


class PaymentOut(BaseModel):
    paid_by_name: str | None
    paid_at: datetime
    # The paid requests still linked in the month; lower after an undo (FR-015).
    count_today: int


class AlertOut(BaseModel):
    """«تراجع بعد الدفع»: an undo of a paid request after the payment (research R6)."""

    number_label: str
    at: datetime
    reason: str


class ReportRowOut(BaseModel):
    marketer_id: int
    marketer_name: str
    count: int
    without_commission: int
    paid_before: int
    tier_min_count: int
    rate: int
    amount: int
    payable: bool
    payment: PaymentOut | None
    alerts: list[AlertOut]


class ReportOut(BaseModel):
    month: str
    month_label: str
    finished: bool
    total_amount: int
    rows: list[ReportRowOut]


class DetailLine(BaseModel):
    """One request behind a row. Allow-list: no phone, username, identity number, card field or
    image (FR-010, research R9). `linked_at` is null for a paid request undone later."""

    id: int
    number_label: str
    full_name: str | None
    type: str
    tower_name: str
    tower_code: str
    linked_at: datetime | None


class PaidBeforeLine(DetailLine):
    paid_month: str


class DetailOut(BaseModel):
    counted: list[DetailLine]
    without_commission: list[DetailLine]
    paid_before: list[PaidBeforeLine]


class PayIn(BaseModel):
    """The figures the confirmation showed; the server refuses when they changed (research R5)."""

    count: int = Field(ge=0)
    amount: int = Field(ge=0)


class MonthSummaryItem(BaseModel):
    marketer_id: int
    count: int
    amount: int


class MonthSummary(BaseModel):
    """«المسوّقون»: this month only, no payment (FR-019)."""

    month_label: str
    items: list[MonthSummaryItem]
