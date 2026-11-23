from datetime import UTC, datetime, timedelta

from app.core.timeutil import baghdad_month_bounds, baghdad_month_label, utc_now


def test_utc_now_is_aware_utc() -> None:
    now = utc_now()
    assert now.tzinfo is not None and now.utcoffset() == timedelta(0)


def test_utc_now_follows_frozen_clock(frozen_clock) -> None:
    frozen_clock.set(datetime(2026, 1, 1, tzinfo=UTC))
    assert utc_now() == datetime(2026, 1, 1, tzinfo=UTC)
    frozen_clock.advance(timedelta(days=29))
    assert utc_now() == datetime(2026, 1, 30, tzinfo=UTC)


def test_month_bounds_just_before_baghdad_midnight() -> None:
    # 20:59:59 UTC on 30 Nov = 23:59:59 in Baghdad (UTC+3) → still November.
    start, end = baghdad_month_bounds(datetime(2026, 11, 30, 20, 59, 59, tzinfo=UTC))
    assert start == datetime(2026, 10, 31, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 11, 30, 21, 0, tzinfo=UTC)


def test_month_bounds_at_baghdad_midnight_on_the_1st() -> None:
    start, end = baghdad_month_bounds(datetime(2026, 11, 30, 21, 0, tzinfo=UTC))
    assert start == datetime(2026, 11, 30, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 12, 31, 21, 0, tzinfo=UTC)


def test_month_label_uses_baghdad_time() -> None:
    assert baghdad_month_label(datetime(2026, 11, 30, 20, 59, tzinfo=UTC)) == "تشرين الثاني 2026"
    assert baghdad_month_label(datetime(2026, 11, 30, 21, 0, tzinfo=UTC)) == "كانون الأول 2026"


# --- baghdad_day_bounds (feature 002 audit filter) ----------------------------------------------

from datetime import date  # noqa: E402

from app.core.timeutil import baghdad_day_bounds  # noqa: E402


def test_day_bounds_single_day() -> None:
    start, end = baghdad_day_bounds(date(2026, 11, 22), date(2026, 11, 22))
    assert start == datetime(2026, 11, 21, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 11, 22, 21, 0, tzinfo=UTC)


def test_day_bounds_late_evening_belongs_to_that_day() -> None:
    start, end = baghdad_day_bounds(date(2026, 11, 22), date(2026, 11, 22))
    at_2330_baghdad = datetime(2026, 11, 22, 20, 30, tzinfo=UTC)
    assert start <= at_2330_baghdad < end


def test_day_bounds_across_month_end_and_open_sides() -> None:
    start, end = baghdad_day_bounds(date(2026, 11, 30), date(2026, 12, 1))
    assert start == datetime(2026, 11, 29, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 12, 1, 21, 0, tzinfo=UTC)
    assert baghdad_day_bounds(None, None) == (None, None)
    assert baghdad_day_bounds(date(2026, 1, 1), None)[1] is None


# --- today's bounds (specs/010 research R10: the admin home counts) ---

from app.core.timeutil import baghdad_today_bounds  # noqa: E402


def test_today_bounds_at_23_30_baghdad_is_that_baghdad_day() -> None:
    at = datetime(2026, 11, 23, 20, 30, tzinfo=UTC)  # 23:30 in Baghdad (UTC+3)
    start, end = baghdad_today_bounds(at)
    assert start == datetime(2026, 11, 22, 21, 0, tzinfo=UTC)  # 00:00 on 23 Nov, Baghdad
    assert end == start + timedelta(days=1)


def test_today_bounds_just_after_baghdad_midnight_is_the_next_day() -> None:
    # 00:30 on 24 Nov in Baghdad is still 23 Nov in UTC.
    at = datetime(2026, 11, 23, 21, 30, tzinfo=UTC)
    start, end = baghdad_today_bounds(at)
    assert start == datetime(2026, 11, 23, 21, 0, tzinfo=UTC)
    assert end == datetime(2026, 11, 24, 21, 0, tzinfo=UTC)


def test_today_bounds_default_to_the_application_clock(frozen_clock) -> None:
    start, end = baghdad_today_bounds()
    assert start <= utc_now() < end
