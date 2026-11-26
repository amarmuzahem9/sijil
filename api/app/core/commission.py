"""The tier rule (docs/system.md v1.23 §9, specs/017 research R1). Pure functions, no database.

Tiers are (min_count, rate) pairs. The tier of a count is the one with the highest min_count not
above the count, and its rate applies to the whole count (no marginal steps).
"""

import re
from collections.abc import Sequence
from datetime import date

Tier = tuple[int, int]

_MONTH = re.compile(r"^(\d{4})-(\d{2})$", re.ASCII)


def _sorted(tiers: Sequence[Tier]) -> list[Tier]:
    if not tiers:
        raise ValueError("no tiers")
    return sorted(tiers)


def tier_for(count: int, tiers: Sequence[Tier]) -> Tier:
    """(min_count, rate) of the tier that applies to `count`."""
    if count < 0:
        raise ValueError("negative count")
    chosen = None
    for tier in _sorted(tiers):
        if tier[0] <= count:
            chosen = tier
    if chosen is None:
        # 004 validation makes the first tier start at 0, so this only guards bad input.
        raise ValueError("no tier for count")
    return chosen


def amount(count: int, tiers: Sequence[Tier]) -> int:
    return tier_for(count, tiers)[1] * count


def next_tier(count: int, tiers: Sequence[Tier]) -> tuple[int, int] | None:
    """(links still needed, rate of the next tier), or None in the top tier («باقيلك»)."""
    tier_for(count, tiers)
    for min_count, rate in _sorted(tiers):
        if min_count > count:
            return min_count - count, rate
    return None


def month_key(month: date) -> str:
    return f"{month.year:04d}-{month.month:02d}"


def parse_month(value: str) -> date:
    """`YYYY-MM` (Latin digits) → the first day of that month. Raises ValueError."""
    match = _MONTH.match(value or "")
    if not match:
        raise ValueError("bad month")
    year, month = int(match[1]), int(match[2])
    if not 1 <= month <= 12:
        raise ValueError("bad month")
    return date(year, month, 1)
