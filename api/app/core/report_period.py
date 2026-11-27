"""The report period in Baghdad days (docs/system.md v1.25 §11; specs/019 research R2).

«هذا الأسبوع» starts on Saturday, «هذا الشهر» on the 1st, both running through today; «مدة محددة» is
two whole Baghdad days, both included. Bounds are returned in UTC as a half-open [start, end).
There is no maximum length (owner, analysis M2).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from app.core.timeutil import baghdad_day_bounds

PeriodKind = Literal["week", "month", "range"]
PERIOD_KINDS: tuple[str, ...] = ("week", "month", "range")

# date.weekday(): Monday = 0 … Saturday = 5.
_SATURDAY = 5


class PeriodError(ValueError):
    """The period cannot be used (an unknown kind, a missing date, `from` after `to`)."""


def week_start(today: date) -> date:
    """The Saturday on or before `today`."""
    return today - timedelta(days=(today.weekday() - _SATURDAY) % 7)


def period_bounds(
    kind: PeriodKind,
    *,
    today: date,
    from_: date | None = None,
    to: date | None = None,
) -> tuple[datetime, datetime]:
    if kind == "week":
        first, last = week_start(today), today
    elif kind == "month":
        first, last = today.replace(day=1), today
    elif kind == "range":
        if from_ is None or to is None or from_ > to:
            raise PeriodError(kind)
        first, last = from_, to
    else:
        raise PeriodError(kind)
    start, end = baghdad_day_bounds(first, last)
    assert start is not None and end is not None
    return start.astimezone(UTC), end.astimezone(UTC)
