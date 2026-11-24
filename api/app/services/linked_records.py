"""The records a pending request is linked to, as the review file shows them (docs/system.md §6.4,
specs/010 research R8, data-model.md › LinkedRecord).

A registry like the match sources of match_service: each source resolves its own refs. In 010 only
`sijil` (submitted requests) is registered; 014 and 015 register `legacy` and `sas`, and SAS fills
`expiry` («حسب آخر استيراد»). A ref with no resolver or no row comes back `available=False`, and the
page shows «سجل غير متوفر». A deleted Sijil request comes back `available=False, deleted=True` with
its request number only, and the page shows «سجل محذوف» (specs/011 R10).

Only review admins ever receive these records (FR-004). They carry no national ID, family number,
card fields or readings.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.matches import MatchRef
from app.models import Request, RequestImage


@dataclass(frozen=True)
class LinkedRecord:
    source: str
    ref: str
    available: bool
    full_name: str | None = None
    username: str | None = None
    phone: str | None = None
    tower_code: str | None = None
    tower_name: str | None = None
    registered_at: datetime | None = None
    status: str | None = None
    image_ids: list[uuid.UUID] = field(default_factory=list)
    expiry: date | None = None
    # specs/011 R10: «سجل محذوف (#T3C-…)».
    deleted: bool = False
    number_label: str | None = None


Resolver = Callable[[Session, list[MatchRef]], dict[MatchRef, LinkedRecord]]
_RESOLVERS: dict[str, Resolver] = {}


def register_resolver(source: str, resolver: Resolver) -> None:
    _RESOLVERS[source] = resolver


def unregister_resolver(source: str) -> None:
    _RESOLVERS.pop(source, None)


def resolve(db: Session, refs: list[MatchRef]) -> dict[MatchRef, LinkedRecord]:
    by_source: dict[str, list[MatchRef]] = {}
    for ref in refs:
        by_source.setdefault(ref.source, []).append(ref)
    found: dict[MatchRef, LinkedRecord] = {}
    for source, group in by_source.items():
        resolver = _RESOLVERS.get(source)
        if resolver is not None:
            found.update(resolver(db, group))
    return {
        ref: found.get(ref) or LinkedRecord(ref.source, ref.ref_id, available=False) for ref in refs
    }


def _sijil(db: Session, refs: list[MatchRef]) -> dict[MatchRef, LinkedRecord]:
    ids = [int(r.ref_id) for r in refs if r.ref_id.isdigit()]
    if not ids:
        return {}
    rows = db.scalars(select(Request).where(Request.id.in_(ids))).all()
    deleted = {
        MatchRef("sijil", str(row.id)): LinkedRecord(
            source="sijil",
            ref=str(row.id),
            available=False,
            deleted=True,
            number_label=row.number_label,
        )
        for row in rows
        if row.is_deleted
    }
    rows = [row for row in rows if not row.is_deleted]
    images: dict[int, list[uuid.UUID]] = {}
    for image in db.scalars(
        select(RequestImage)
        .where(RequestImage.request_id.in_(ids))
        .order_by(RequestImage.side.desc())  # front before back
    ):
        images.setdefault(image.request_id, []).append(image.id)
    return deleted | {
        MatchRef("sijil", str(row.id)): LinkedRecord(
            source="sijil",
            ref=str(row.id),
            available=True,
            number_label=row.number_label,
            full_name=row.full_name,
            username=row.username,
            phone=row.phone,
            tower_code=row.tower_code,
            tower_name=row.tower_name,
            registered_at=row.submitted_at,
            status=row.status,
            image_ids=images.get(row.id, []),
            expiry=None,
        )
        for row in rows
    }


register_resolver("sijil", _sijil)
