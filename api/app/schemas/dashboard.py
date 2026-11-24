"""The marketer home (docs/system.md v1.18 §4.2, specs/013 contracts/api.md › dashboard)."""

from datetime import datetime

from pydantic import BaseModel


class RecentLink(BaseModel):
    id: int
    number_label: str
    full_name: str | None
    linked_at: datetime


class MarketerDashboard(BaseModel):
    # Links of this Baghdad month that count for commission (owner, Q1).
    linked_this_month: int
    # Returns accepted with «لا» for commission, shown as «و M بلا عمولة».
    linked_without_commission: int
    month_label: str
    # Up to 10 of this month, newest link first.
    recent_links: list[RecentLink]
