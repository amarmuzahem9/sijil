"""The subscriber's file (docs/system.md v1.24 §10 item 4; specs/018 research R5–R9).

One record — a request, a legacy subscriber or a SAS subscriber — with every record linked to it
by the §6.1 keys and the reason of each link, strongest first, and a request's history read from
the stored facts. Records are never merged (owner Q1). Read-only (owner Q3).

The response is built key by key, as an allow-list: national ID, family number, card fields and
image ids are added only for the main admin and `review` (owner Q2); for anyone else the keys are
absent, not null (research R7).
"""

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    LegacyImage,
    LegacySubscriber,
    Request,
    RequestImage,
    RequestLink,
    RequestNumberPin,
    SasSubscriber,
    Tower,
    User,
)
from app.services.legacy_source import SHOWN_EXTRA
from app.services.review_service import can_review
from app.services.subscriber_search import Row, legacy_row, request_row, sas_row

LINKED_LIMIT = 50
_STRENGTH = {"same_person": 0, "same_phone": 1, "same_family": 2}
SOURCES = ("sijil", "legacy", "sas")


@dataclass(frozen=True)
class Keys:
    phones: frozenset[str]
    national_id: str | None
    family_key: str | None


# --- the record ----------------------------------------------------------------------------------


def _ref(ref: str) -> int:
    if not ref.lstrip("-").isdigit():
        raise AppError("not_found", 404)
    return int(ref)


def _names(db: Session, ids) -> dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.name).where(User.id.in_(ids))).all())


def _request_record(db: Session, r: Request, entitled: bool) -> tuple[dict, Keys]:
    base = asdict(request_row(r))
    base.update(type=r.type, marketer_name=r.marketer.name)
    if r.is_deleted:
        # The kept fields only (specs/011): number, marketer, type, status at deletion, dates,
        # tower and plan. No identity key at all, whoever asks.
        base.update(
            status=r.status,
            tower_name=r.tower_name,
            tower_code=r.tower_code,
            registered_at=r.submitted_at,
            username=None,
        )
        return base, Keys(frozenset(), None, None)
    base["username"] = r.username
    if entitled:
        base["national_id"] = r.national_id
        base["family_number"] = r.family_number
        base["card_fields"] = {
            "birth_date": r.birth_date,
            "issue_date": r.issue_date,
            "expiry_date": r.expiry_date,
            "birth_place": r.birth_place,
            "issuing_authority": r.issuing_authority,
        }
        images = db.scalars(
            select(RequestImage).where(RequestImage.request_id == r.id).order_by(RequestImage.side)
        ).all()
        base["images"] = [{"id": str(i.id), "side": i.side} for i in images]
    phones = frozenset(p for p in (r.phone,) if p)
    return base, Keys(phones, r.national_id, r.family_key)


def _legacy_record(db: Session, s: LegacySubscriber, entitled: bool) -> tuple[dict, Keys]:
    base = asdict(legacy_row(s))
    base.update(
        legacy_number=s.legacy_number,
        status_text=s.status_text,
        counts_in_check=s.counts_in_check,
        # The shown extra data of 014 R12, never the e-mails.
        extra={key: (s.extra or {}).get(key) for key in SHOWN_EXTRA},
        incomplete=s.incomplete,
    )
    if entitled:
        base["family_number"] = s.family_number
        images = db.scalars(
            select(LegacyImage)
            .where(LegacyImage.legacy_subscriber_id == s.id)
            .order_by(LegacyImage.side)
        ).all()
        base["images"] = [{"id": str(i.id), "side": i.side} for i in images]
    phones = frozenset(p for p in (s.phone,) if p)
    return base, Keys(phones, None, s.family_key)


def _sas_record(db: Session, s: SasSubscriber) -> tuple[dict, Keys]:
    tower = db.get(Tower, s.tower_id) if s.tower_id else None
    base = asdict(sas_row(s, tower))
    base.update(
        username=s.username,
        expires_at=s.expires_at,
        group_name=s.group_name,
        last_online_at=s.last_online_at,
        missing_since=s.missing_since,
        username_phone=s.username_phone,
        # SAS holds no document in Sijil: «بلا مستمسكات في سِجلّ».
        no_documents=True,
    )
    phones = frozenset(p for p in (s.phone, s.username_phone) if p)
    return base, Keys(phones, None, None)


# --- linked records (research R5) ----------------------------------------------------------------


def _reason(keys: Keys, phones: set[str], national_id=None, family=None) -> str | None:
    if (
        keys.national_id
        and keys.family_key
        and (national_id, family)
        == (
            keys.national_id,
            keys.family_key,
        )
    ):
        return "same_person"
    if keys.phones & phones:
        return "same_phone"
    if keys.family_key and family == keys.family_key:
        return "same_family"
    return None


def _linked(db: Session, keys: Keys, source: str, ref: int) -> tuple[list[dict], int]:
    found: list[tuple[str, Row]] = []
    phones = list(keys.phones)

    conditions = []
    if phones:
        conditions.append(Request.phone.in_(phones))
    if keys.family_key:
        conditions.append(Request.family_key == keys.family_key)
    if conditions:
        query = select(Request).where(Request.deleted_at.is_(None), or_(*conditions))
        if source == "sijil":
            query = query.where(Request.id != ref)
        for r in db.scalars(query):
            reason = _reason(keys, {r.phone}, r.national_id, r.family_key)
            if reason:
                found.append((reason, request_row(r)))

    conditions = []
    if phones:
        conditions.append(LegacySubscriber.phone.in_(phones))
    if keys.family_key:
        conditions.append(LegacySubscriber.family_key == keys.family_key)
    if conditions:
        query = select(LegacySubscriber).where(or_(*conditions))
        if source == "legacy":
            query = query.where(LegacySubscriber.id != ref)
        for s in db.scalars(query):
            reason = _reason(keys, {s.phone}, None, s.family_key)
            if reason:
                found.append((reason, legacy_row(s)))

    if phones:
        query = (
            select(SasSubscriber, Tower)
            .outerjoin(Tower, Tower.id == SasSubscriber.tower_id)
            .where(or_(SasSubscriber.phone.in_(phones), SasSubscriber.username_phone.in_(phones)))
        )
        if source == "sas":
            query = query.where(SasSubscriber.id != ref)
        for s, tower in db.execute(query):
            found.append(("same_phone", sas_row(s, tower)))

    def order(item: tuple[str, Row]):
        reason, row = item
        at = row.registered_at.timestamp() if row.registered_at else 0
        return (_STRENGTH[reason], -at, row.source, int(row.ref))

    found.sort(key=order)
    shown = [{"reason": reason, "row": asdict(row)} for reason, row in found[:LINKED_LIMIT]]
    return shown, max(0, len(found) - LINKED_LIMIT)


# --- history (research R9) -----------------------------------------------------------------------


def _history(db: Session, r: Request, entitled: bool) -> list[dict[str, Any]]:
    pins = db.scalars(
        select(RequestNumberPin)
        .where(RequestNumberPin.request_id == r.id)
        .order_by(RequestNumberPin.pinned_at, RequestNumberPin.id)
    ).all()
    links = db.scalars(
        select(RequestLink)
        .where(RequestLink.request_id == r.id)
        .order_by(RequestLink.at, RequestLink.id)
    ).all()
    names = _names(
        db,
        [r.marketer_id, r.approved_by, r.rejected_by, r.deleted_by]
        + [p.pinned_by for p in pins]
        + [link.actor_id for link in links],
    )
    events: list[dict[str, Any]] = [
        {"kind": "submitted", "at": r.submitted_at, "by_name": names.get(r.marketer_id)}
    ]
    if r.approved_at is not None:
        events.append(
            {"kind": "approved", "at": r.approved_at, "by_name": names.get(r.approved_by)}
        )
    if r.rejected_at is not None:
        events.append(
            {
                "kind": "rejected",
                "at": r.rejected_at,
                "by_name": names.get(r.rejected_by),
                "reason": r.rejection_reason,
            }
        )
    for p in pins:
        event = {"kind": "pinned", "at": p.pinned_at, "by_name": names.get(p.pinned_by)}
        if entitled:
            event["field"] = p.field  # which number, never its value
        events.append(event)
    for link in links:
        event = {"kind": link.kind, "at": link.at, "by_name": names.get(link.actor_id)}
        if link.kind == "unlinked":
            event["reason"] = link.reason
        events.append(event)
    if r.deleted_at is not None:
        events.append(
            {
                "kind": "deleted",
                "at": r.deleted_at,
                "by_name": names.get(r.deleted_by),
                "reason": r.deletion_reason,
            }
        )
    # Stable: equal times keep the order above (an automatic acceptance at submission time).
    return sorted(events, key=lambda e: e["at"])


# --- the file ------------------------------------------------------------------------------------


def build(db: Session, user: User, source: str, ref: str) -> dict[str, Any]:
    if source not in SOURCES:
        raise AppError("not_found", 404)
    rid = _ref(ref)
    entitled = can_review(user)
    history: list[dict] = []
    if source == "sijil":
        r = db.get(Request, rid)
        if r is None:
            raise AppError("not_found", 404)
        record, keys = _request_record(db, r, entitled)
        history = _history(db, r, entitled)
    elif source == "legacy":
        s = db.get(LegacySubscriber, rid)
        if s is None:
            raise AppError("not_found", 404)
        record, keys = _legacy_record(db, s, entitled)
    else:
        s = db.get(SasSubscriber, rid)
        if s is None:
            raise AppError("not_found", 404)
        record, keys = _sas_record(db, s)
    linked, more = _linked(db, keys, source, rid)
    return {"record": record, "history": history, "linked": linked, "more_linked": more}
