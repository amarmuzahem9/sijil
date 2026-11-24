"""Imported legacy subscribers as a check source and as linked records of the review file
(docs/system.md §6, §6.1 notes, §6.4; specs/014 US2, US3, research R2, R3, R12).

Registered as `legacy` in the match_service registry, next to `sijil`, so the early checks, the
authoritative check at submission and the 010 re-check after a pin all see them. A legacy
subscriber has no national ID: it matches on phone (§8.1) and family key (§6.2) only, so a phone
match gives case 1 and a family match case 3. It is never pending (it cannot block a return).
Rows with «ملغي» or «مرفوض» (`counts_in_check = false`) never match. Nothing here reaches the
marketer: callers only see the flags of the match.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.matches import Matches, MatchRecord, MatchRef
from app.models import LegacyImage, LegacySubscriber
from app.services import linked_records, match_service
from app.services.linked_records import LinkedRecord


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


# --- the review file (specs/014 US3, research R12) ------------------------------------------------

# Shown to review admins as «بيانات إضافية»; the e-mail columns are stored but never shown.
SHOWN_EXTRA = ("mother_name", "mother_father_name", "birth_date")


def _resolve(db: Session, refs: list[MatchRef]) -> dict[MatchRef, LinkedRecord]:
    ids = [int(r.ref_id) for r in refs if r.ref_id.isdigit()]
    if not ids:
        return {}
    images: dict[int, list] = {}
    for image in db.scalars(
        select(LegacyImage)
        .where(LegacyImage.legacy_subscriber_id.in_(ids))
        .order_by(LegacyImage.side.desc())  # front before back
    ):
        images.setdefault(image.legacy_subscriber_id, []).append(image.id)
    return {
        MatchRef("legacy", str(row.id)): LinkedRecord(
            source="legacy",
            ref=str(row.id),
            available=True,
            full_name=row.full_name,
            phone=row.phone,
            registered_at=row.form_submitted_at,
            status=row.status_text,
            image_ids=images.get(row.id, []),
            legacy_number=row.legacy_number,
            incomplete=row.incomplete,
            extra={key: row.extra.get(key) for key in SHOWN_EXTRA},
        )
        for row in db.scalars(select(LegacySubscriber).where(LegacySubscriber.id.in_(ids)))
    }


linked_records.register_resolver("legacy", _resolve)
