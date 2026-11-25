"""When the nightly backup is due (specs/016 FR-005, research R5).

Once per Baghdad day, at or after BACKUP_NIGHTLY_AT, catching up after a restart. A failed
attempt is tried again an hour later, at most 3 attempts in a Baghdad day, so a full disk or a
broken database does not loop every 15 seconds.
"""

from datetime import datetime, timedelta

from app.core.timeutil import BAGHDAD

RETRY_AFTER = timedelta(hours=1)
MAX_ATTEMPTS_PER_DAY = 3


def nightly_due(now: datetime, nightly_minutes: int, attempts: list[tuple[datetime, bool]]) -> bool:
    """`attempts`: (start time, succeeded) of every nightly attempt, from the backup files."""
    local = now.astimezone(BAGHDAD)
    if local.hour * 60 + local.minute < nightly_minutes:
        return False
    today = [(at, ok) for at, ok in attempts if at.astimezone(BAGHDAD).date() == local.date()]
    if any(ok for _, ok in today):
        return False
    if len(today) >= MAX_ATTEMPTS_PER_DAY:
        return False
    return not any(now - at < RETRY_AFTER for at, _ in today)
