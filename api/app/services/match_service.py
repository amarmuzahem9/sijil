"""The check engine: who already has this phone, national ID or family number?
(docs/system.md §6, §6.2; specs/008 research R2; specs/009 research R1.)

Every registered source is asked and returns one `MatchRecord` per matching record, flagging which
of the keys it holds and whether it is still pending review. In 009 the only source is `sijil`:
submitted requests that are pending review, approved or linked. Rejected requests and drafts never
count (system.md v1.9). Features 013/014 register `legacy` and `sas` here with the same contract: a
record with no national ID or no family number simply never sets that flag. Callers pass keys
already normalized (phone §8.1, national ID 12 digits, family key §6.2); a None key never matches.
"""

from collections.abc import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.matches import Matches, MatchRecord, MatchRef
from app.models import Request
from app.models.request import ACTIVE_STATUSES
from app.services import settings_service

Source = Callable[..., Matches]
_SOURCES: dict[str, Source] = {}


def register_source(name: str, source: Source) -> None:
    _SOURCES[name] = source


def unregister_source(name: str) -> None:
    _SOURCES.pop(name, None)


def find_matches(
    db: Session,
    *,
    phone: str | None = None,
    national_id: str | None = None,
    family_key: str | None = None,
) -> Matches:
    found = Matches()
    if phone is None and national_id is None and family_key is None:
        return found
    for source in _SOURCES.values():
        found.extend(source(db, phone=phone, national_id=national_id, family_key=family_key))
    return found


def _sijil_source(
    db: Session, *, phone: str | None, national_id: str | None, family_key: str | None
) -> Matches:
    keys = [
        (column, value)
        for column, value in (
            (Request.phone, phone),
            (Request.national_id, national_id),
            (Request.family_key, family_key),
        )
        if value is not None
    ]
    if not keys:
        return Matches()
    rows = db.execute(
        select(Request.id, Request.phone, Request.national_id, Request.family_key, Request.status)
        .where(
            or_(*(column == value for column, value in keys)), Request.status.in_(ACTIVE_STATUSES)
        )
        .order_by(Request.id)
    )
    return Matches(
        [
            MatchRecord(
                "sijil",
                str(row.id),
                phone=phone is not None and row.phone == phone,
                national_id=national_id is not None and row.national_id == national_id,
                family=family_key is not None and row.family_key == family_key,
                pending=row.status == "pending_review",
            )
            for row in rows
        ]
    )


register_source("sijil", _sijil_source)


# --- catalog usage (004 registry; research R9): any request, of any status, uses its choices.


def _usage(column) -> Callable[[Session, int], int]:
    def check(db: Session, item_id: int) -> int:
        return db.scalar(select(func.count()).select_from(Request).where(column == item_id)) or 0

    return check


settings_service.register_usage_check("area", _usage(Request.area_id))
settings_service.register_usage_check("tower", _usage(Request.tower_id))
settings_service.register_usage_check("plan", _usage(Request.plan_id))

__all__ = [
    "MatchRecord",
    "MatchRef",
    "Matches",
    "find_matches",
    "register_source",
    "unregister_source",
]
