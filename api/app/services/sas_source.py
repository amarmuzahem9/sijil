"""Imported SAS subscribers as a check source and as linked records of the review file
(docs/system.md 1.20 §12.2, §6.1, §6.4; specs/015 US2, US3, research R8, R13).

Registered as `sas` in the match_service registry, next to `sijil` and `legacy`, so the early
checks, the authoritative check at submission and the 010 re-check after a pin all see them. A SAS
subscriber has no national ID and no family number: it matches on phone only, through the phone
column or the phone inside the username (FR-012), so a match is case 1. It is never pending (it
cannot block a return). Rows marked «غير موجود في آخر ملف» still count (FR-022). Nothing here
reaches the marketer: callers only see the flags of the match.
"""

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.matches import Matches, MatchRecord, MatchRef
from app.core.timeutil import BAGHDAD
from app.models import SasImport, SasSubscriber, SasTowerMapping, Tower
from app.services import linked_records, match_service, settings_service
from app.services.linked_records import LinkedRecord


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


# --- the review file (specs/015 US3, research R13) ----------------------------------------------


def _baghdad_date(value: datetime | None) -> date | None:
    return value.astimezone(BAGHDAD).date() if value else None


def _resolve(db: Session, refs: list[MatchRef]) -> dict[MatchRef, LinkedRecord]:
    """Review admins only. Never notes, parent_name, a national ID, a family number or images;
    the tower shows its current name."""
    ids = [int(r.ref_id) for r in refs if r.ref_id.isdigit()]
    if not ids:
        return {}
    rows = db.execute(
        select(SasSubscriber, Tower, SasImport.created_at)
        .outerjoin(Tower, Tower.id == SasSubscriber.tower_id)
        .join(SasImport, SasImport.id == SasSubscriber.last_import_id)
        .where(SasSubscriber.id.in_(ids))
    )
    return {
        MatchRef("sas", str(sub.id)): LinkedRecord(
            source="sas",
            ref=str(sub.id),
            available=True,
            full_name=sub.full_name,
            username=sub.username,
            phone=sub.phone,
            username_phone=sub.username_phone if sub.username_phone != sub.phone else None,
            tower_code=tower.code if tower else None,
            tower_name=tower.name if tower else None,
            registered_at=sub.sas_created_at,
            expiry=_baghdad_date(sub.expires_at),
            expiry_as_of=_baghdad_date(imported_at),
            last_online=sub.last_online_at,
            group_name=sub.group_name,
            missing_from_file=_baghdad_date(sub.missing_since),
        )
        for sub, tower, imported_at in rows
    }


linked_records.register_resolver("sas", _resolve)


# --- tower usage (specs/015 research R15; system.md §10 item 6) ---------------------------------


def _tower_usage(db: Session, tower_id: int) -> int:
    """A tower that a SAS subscriber or a prefix mapping points to is in use: it cannot be deleted
    and its code is locked, or the username rule would silently stop resolving."""
    subscribers = db.scalar(
        select(func.count()).select_from(SasSubscriber).where(SasSubscriber.tower_id == tower_id)
    )
    mappings = db.scalar(
        select(func.count())
        .select_from(SasTowerMapping)
        .where(SasTowerMapping.tower_id == tower_id)
    )
    return (subscribers or 0) + (mappings or 0)


settings_service.register_usage_check("tower", _tower_usage)
