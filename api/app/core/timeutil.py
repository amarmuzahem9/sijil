"""The single application clock (research.md R11) and Baghdad-time helpers (Principle X)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

BAGHDAD = ZoneInfo("Asia/Baghdad")

ARABIC_MONTHS = (
    "كانون الثاني",
    "شباط",
    "آذار",
    "نيسان",
    "أيار",
    "حزيران",
    "تموز",
    "آب",
    "أيلول",
    "تشرين الأول",
    "تشرين الثاني",
    "كانون الأول",
)

_override: datetime | None = None


def utc_now() -> datetime:
    """Current time in UTC. Every time used in business logic MUST come from here."""
    return _override if _override is not None else datetime.now(UTC)


def _set_clock_for_tests(value: datetime | None) -> None:
    """Test hook only (see tests/conftest.py `frozen_clock`)."""
    global _override
    if value is not None and value.tzinfo is None:
        raise ValueError("clock override must be timezone-aware")
    _override = value.astimezone(UTC) if value is not None else None


def baghdad_month_bounds(at: datetime | None = None) -> tuple[datetime, datetime]:
    """[start, end) of the Baghdad calendar month containing `at`, returned in UTC."""
    local = (at or utc_now()).astimezone(BAGHDAD)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start.astimezone(UTC), nxt.astimezone(UTC)


def baghdad_month_label(at: datetime | None = None) -> str:
    local = (at or utc_now()).astimezone(BAGHDAD)
    return f"{ARABIC_MONTHS[local.month - 1]} {local.year}"
