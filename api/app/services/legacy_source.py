"""Imported legacy subscribers as a check source (docs/system.md §6, §6.1 notes; specs/014 US2,
research R2, R3).

Registered as `legacy` in the match_service registry, next to `sijil`, so the early checks, the
authoritative check at submission and the 010 re-check after a pin all see them. A legacy
subscriber has no national ID: it matches on phone (§8.1) and family key (§6.2) only, so a phone
match gives case 1 and a family match case 3. It is never pending (it cannot block a return).
Rows with «ملغي» or «مرفوض» (`counts_in_check = false`) never match. Nothing here reaches the
marketer: callers only see the flags of the match.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.matches import Matches, MatchRecord
from app.models import LegacySubscriber
from app.services import match_service


def _legacy_source(
    db: Session, *, phone: str | None, national_id: str | None, family_key: str | None
) -> Matches:
    del national_id  # legacy subscribers have none (§12.1)
    keys = [
        (column, value)
        for column, value in (
            (LegacySubscriber.phone, phone),
            (LegacySubscriber.family_key, family_key),
        )
        if value is not None
    ]
    if not keys:
        return Matches()
    rows = db.execute(
        select(LegacySubscriber.id, LegacySubscriber.phone, LegacySubscriber.family_key)
        .where(or_(*(column == value for column, value in keys)), LegacySubscriber.counts_in_check)
        .order_by(LegacySubscriber.id)
    )
    return Matches(
        [
            MatchRecord(
                "legacy",
                str(row.id),
                phone=phone is not None and row.phone == phone,
                family=family_key is not None and row.family_key == family_key,
            )
            for row in rows
        ]
    )


match_service.register_source("legacy", _legacy_source)
