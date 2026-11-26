"""The marketer home (docs/system.md v1.23 §4.2, specs/013 and specs/017 contracts/api.md ›
dashboard)."""

from datetime import datetime

from pydantic import BaseModel


class RecentLink(BaseModel):
    id: int
    number_label: str
    full_name: str | None
    linked_at: datetime


class NextTier(BaseModel):
    """«باقيلك {remaining} وتصير {rate} للمشترك» (specs/017 FR-006)."""

    remaining: int
    rate: int


class MarketerDashboard(BaseModel):
    # Links of this Baghdad month that count for commission (owner, Q1).
    linked_this_month: int
    # Returns accepted with «لا», and requests already paid in an earlier month (specs/017
    # FR-003, FR-016), shown as «و M بلا عمولة».
    linked_without_commission: int
    month_label: str
    # The tier and the expected amount by today's tiers (specs/017 US1); null in the top tier.
    tier_rate: int
    expected_amount: int
    next_tier: NextTier | None
    # Up to 10 of this month, newest link first.
    recent_links: list[RecentLink]
