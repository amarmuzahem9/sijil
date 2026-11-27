"""The report period in Baghdad days (docs/system.md v1.25 §11; specs/019 research R2,
analysis M2)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.report_period import PeriodError, period_bounds
from app.core.timeutil import BAGHDAD


def _utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    """A Baghdad wall-clock time, as UTC."""
    return datetime(y, m, d, hh, mm, tzinfo=BAGHDAD).astimezone(UTC)


# 2026-11-27 is a Friday, 2026-11-28 a Saturday.


def test_week_on_saturday_starts_that_day() -> None:
    start, end = period_bounds("week", today=date(2026, 11, 28))
    assert start == _utc(2026, 11, 28)
    assert end == _utc(2026, 11, 29)


def test_week_on_friday_starts_the_saturday_before() -> None:
    start, end = period_bounds("week", today=date(2026, 11, 27))
    assert start == _utc(2026, 11, 21)
    assert end == _utc(2026, 11, 28)


def test_month_starts_on_the_first_and_runs_through_today() -> None:
    start, end = period_bounds("month", today=date(2026, 11, 27))
    assert start == _utc(2026, 11, 1)
    assert end == _utc(2026, 11, 28)


def test_month_on_the_first() -> None:
    start, end = period_bounds("month", today=date(2026, 12, 1))
    assert start == _utc(2026, 12, 1)
    assert end == _utc(2026, 12, 2)


def test_range_includes_both_days() -> None:
    start, end = period_bounds(
        "range", today=date(2026, 11, 27), from_=date(2026, 10, 1), to=date(2026, 10, 31)
    )
    assert start == _utc(2026, 10, 1)
    assert end == _utc(2026, 11, 1)
    last_minute = _utc(2026, 10, 31, 23, 59)
    next_day = _utc(2026, 11, 1, 0, 0)
    assert start <= last_minute < end
    assert not (start <= next_day < end)


def test_single_day_range() -> None:
    start, end = period_bounds(
        "range", today=date(2026, 11, 27), from_=date(2026, 11, 3), to=date(2026, 11, 3)
    )
    assert end - start == timedelta(days=1)


def test_bounds_are_utc() -> None:
    start, end = period_bounds("month", today=date(2026, 11, 27))
    assert start.tzinfo == UTC and end.tzinfo == UTC
    # Baghdad is UTC+3: midnight 1 November Baghdad is 21:00 on 31 October UTC.
    assert start == datetime(2026, 10, 31, 21, 0, tzinfo=UTC)


def test_long_range_is_accepted() -> None:
    """No maximum length (owner, analysis M2): the 5,000-row export limit is enough."""
    start, end = period_bounds(
        "range", today=date(2026, 11, 27), from_=date(2021, 1, 1), to=date(2026, 11, 27)
    )
    assert start == _utc(2021, 1, 1)
    assert end == _utc(2026, 11, 28)


@pytest.mark.parametrize(
    ("from_", "to"),
    [
        (date(2026, 11, 2), date(2026, 11, 1)),  # from after to
        (None, date(2026, 11, 1)),
        (date(2026, 11, 1), None),
        (None, None),
    ],
)
def test_invalid_range(from_, to) -> None:
    with pytest.raises(PeriodError):
        period_bounds("range", today=date(2026, 11, 27), from_=from_, to=to)


def test_unknown_kind() -> None:
    with pytest.raises(PeriodError):
        period_bounds("year", today=date(2026, 11, 27))  # type: ignore[arg-type]
