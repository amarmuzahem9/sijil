"""Imported SAS subscribers as a check source (docs/system.md 1.20 §12.2, §6.1; specs/015 US2,
research R8).

Registered as `sas` in the match_service registry, next to `sijil` and `legacy`, so the early
checks, the authoritative check at submission and the 010 re-check after a pin all see them. A SAS
subscriber has no national ID and no family number: it matches on phone only, through the phone
column or the phone inside the username (FR-012), so a match is case 1. It is never pending (it
cannot block a return). Rows marked «غير موجود في آخر ملف» still count (FR-022). Nothing here
reaches the marketer: callers only see the flags of the match.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.matches import Matches, MatchRecord
from app.models import SasSubscriber
from app.services import match_service


def _sas_source(
    db: Session, *, phone: str | None, national_id: str | None, family_key: str | None
) -> Matches:
    del national_id, family_key  # SAS subscribers have neither (§12.2)
    if phone is None:
        return Matches()
    ids = db.scalars(
        select(SasSubscriber.id)
        .where(or_(SasSubscriber.phone == phone, SasSubscriber.username_phone == phone))
        .order_by(SasSubscriber.id)
    )
    return Matches([MatchRecord("sas", str(sid), phone=True) for sid in ids])


match_service.register_source("sas", _sas_source)
