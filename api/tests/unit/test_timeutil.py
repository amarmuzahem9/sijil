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
