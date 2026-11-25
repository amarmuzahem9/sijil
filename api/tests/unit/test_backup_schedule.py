"""When the nightly backup is due (specs/016 FR-005, research R5, T019). Baghdad is UTC+3.

Due once per Baghdad day after BACKUP_NIGHTLY_AT, catching up after a restart. After a failed
attempt it tries again an hour later, at most 3 attempts a day, so a broken disk does not loop.
"""

from datetime import UTC, datetime, timedelta

from app.backup.schedule import nightly_due

AT_3 = 3 * 60  # 03:00 Baghdad


def bg(day: int, hour: int, minute: int = 0) -> datetime:
    """A Baghdad wall-clock time as UTC."""
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC) - timedelta(hours=3)


def test_not_before_the_time() -> None:
    assert nightly_due(bg(25, 2, 59), AT_3, []) is False


def test_due_at_and_after_the_time() -> None:
    assert nightly_due(bg(25, 3, 0), AT_3, []) is True
    assert nightly_due(bg(25, 14, 30), AT_3, []) is True  # catches up after a restart


def test_not_twice_the_same_baghdad_day() -> None:
    done = [(bg(25, 3, 0), True)]
    assert nightly_due(bg(25, 3, 15), AT_3, done) is False
    assert nightly_due(bg(25, 23, 59), AT_3, done) is False
    assert nightly_due(bg(26, 3, 0), AT_3, done) is True


def test_day_boundary_is_baghdad_midnight_not_utc() -> None:
    # 22:30 UTC on the 25th is 01:30 Baghdad on the 26th: before the time on a new day.
    done = [(bg(25, 3, 0), True)]
    late_utc = datetime(2026, 11, 25, 22, 30, tzinfo=UTC)
    assert nightly_due(late_utc, AT_3, done) is False
    # 00:30 Baghdad on the 26th with a 00:15 schedule: a new Baghdad day, still the 25th in UTC.
    assert nightly_due(bg(26, 0, 30), 15, [(bg(25, 0, 15), True)]) is True


def test_failure_retried_after_an_hour_at_most_three_times() -> None:
    failed = [(bg(25, 3, 0), False)]
    assert nightly_due(bg(25, 3, 30), AT_3, failed) is False
    assert nightly_due(bg(25, 4, 0), AT_3, failed) is True
    three = [(bg(25, 3, 0), False), (bg(25, 4, 0), False), (bg(25, 5, 0), False)]
    assert nightly_due(bg(25, 9, 0), AT_3, three) is False
    assert nightly_due(bg(26, 3, 0), AT_3, three) is True


def test_seven_simulated_days_one_nightly_each() -> None:
    # SC-001 locally: a tick every 15 minutes for 7 Baghdad days.
    attempts: list[tuple[datetime, bool]] = []
    tick = bg(20, 0, 0)
    while tick < bg(27, 0, 0):
        if nightly_due(tick, AT_3, attempts):
            attempts.append((tick, True))
        tick += timedelta(minutes=15)
    days = [(t + timedelta(hours=3)).date().day for t, _ in attempts]
    assert days == [20, 21, 22, 23, 24, 25, 26]
    assert all((t + timedelta(hours=3)).hour == 3 for t, _ in attempts)
