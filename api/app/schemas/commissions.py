"""Commission schemas (specs/017 contracts/api.md). Allow-lists: no phone, username, identity
number, card field or image ever goes out (research R9)."""

from pydantic import BaseModel


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
