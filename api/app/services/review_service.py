"""Admin review of pending requests (docs/system.md v1.14 §6.4, §10 item 2; specs/010 research
R1–R9, R13).

Only the main admin and admins with `review` reach these functions (the routes check). Never log or
audit the national ID, the family number, the phone or names (Principle II): log lines carry the
request number and the action only.
"""

import logging
import uuid
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core import rejection_reasons
from app.core.access import has_any_permission
from app.core.matches import Matches, MatchRef
from app.core.review_check import ReviewCheck, review
from app.errors import AppError
from app.models import ImageAccessLog, Request, RequestImage, RequestReason, User
from app.models.draft import NAME_FIELDS
from app.schemas.admin_requests import (
    DecisionOut,
    ImageOut,
    LinkedRecordOut,
    LocationOut,
    NumberOut,
    NumbersOut,
    PendingItem,
    PendingList,
    PinOut,
    ReasonOut,
    RequestFileOut,
)
from app.services import image_store, linked_records, match_service

log = logging.getLogger("sijil.review")


def can_review(user: User) -> bool:
    return has_any_permission(user.role, user.permissions, ["review"])


def _active_codes(request: Request) -> list[str]:
    codes: list[str] = []
    for row in request.reasons:
        if row.state != "not_applicable" and row.reason not in codes:
            codes.append(row.reason)
    return codes


# --- the list (R13) ------------------------------------------------------------------------------


def list_pending(db: Session, reason: str | None = None) -> PendingList:
    query = select(Request).where(Request.status == "pending_review")
    if reason is not None:
        query = query.where(
            exists().where(
                RequestReason.request_id == Request.id,
                RequestReason.reason == reason,
                RequestReason.state != "not_applicable",
            )
        )
    rows = db.scalars(query.order_by(Request.submitted_at, Request.id)).all()
    return PendingList(
        total=len(rows),
        items=[
            PendingItem(
                id=r.id,
                number_label=r.number_label,
                type=r.type,
                reasons=_active_codes(r),
                marketer_name=r.marketer.name,
                full_name=r.full_name,
                tower_code=r.tower_code,
                tower_name=r.tower_name,
                submitted_at=r.submitted_at,
            )
            for r in rows
        ],
    )


# --- the live re-check (R5) ----------------------------------------------------------------------


def _row_ref(row: RequestReason) -> MatchRef | None:
    if row.matched_source is None or row.matched_ref is None:
        return None
    return MatchRef(row.matched_source, row.matched_ref)


def live_check(db: Session, request: Request) -> ReviewCheck:
    """The §6.1 match on the request's current numbers, against every source, the request itself
    left out. Rejected requests never count (match_service)."""
    found = match_service.find_matches(
        db,
        phone=request.phone,
        national_id=request.national_id,
        family_key=request.family_key,
    )
    own = MatchRef("sijil", str(request.id))
    matches = Matches([r for r in found.records if r.ref != own])
    return_rows = [r for r in request.reasons if r.reason == "return"]
    return_refs = [ref for r in return_rows if (ref := _row_ref(r)) is not None]
    basis = next((r.details.get("basis") for r in return_rows if r.details.get("basis")), None)
    prior = {
        ref
        for r in request.reasons
        if r.reason == "numbers_conflict" and r.state == "open" and (ref := _row_ref(r))
    }
    return review(request.type, return_refs, basis, matches, prior)


# --- the file (FR-003, FR-004, FR-012) -----------------------------------------------------------


def get_for_review(db: Session, user: User, request_id: int) -> Request:
    """The request, or the same 404 for a missing one and for a caller without `review`."""
    request = db.get(Request, request_id)
    if request is None or not can_review(user):
        raise AppError("request_not_found", 404)
    return request


def _names(db: Session, ids: set[int | None]) -> dict[int, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(wanted)))}


def _reading(request: Request, field: str) -> str | None:
    return ((request.card_fields or {}).get(field) or {}).get("original")


def _numbers(request: Request, names: dict[int, str]) -> NumbersOut:
    edited = {
        f
        for r in request.reasons
        if r.reason == "numbers_edited"
        for f in r.details.get("fields", [])
    }

    def pins(field: str) -> list[PinOut]:
        return [
            PinOut(value=p.value, source=p.source, by=names.get(p.pinned_by, ""), at=p.pinned_at)
            for p in request.pins
            if p.field == field
        ]

    return NumbersOut(
        national_id=NumberOut(
            reading=_reading(request, "national_id"),
            mrz=(request.national_id_check or {}).get("mrz"),
            marketer=request.submitted_national_id,
            current=request.national_id,
            edited="national_id" in edited,
            pins=pins("national_id"),
        ),
        family_number=NumberOut(
            reading=_reading(request, "family_number"),
            mrz=None,
            marketer=request.submitted_family_number,
            current=request.family_number,
            edited="family_number" in edited,
            pins=pins("family_number"),
        ),
    )


def _reasons(db: Session, request: Request) -> list[ReasonOut]:
    refs = [ref for r in request.reasons if (ref := _row_ref(r)) is not None]
    records = linked_records.resolve(db, refs)
    out: list[ReasonOut] = []
    for row in request.reasons:
        ref = _row_ref(row)
        record = records.get(ref) if ref is not None else None
        out.append(
            ReasonOut(
                reason=row.reason,
                state=row.state,
                added_at_review=row.added_by is not None,
                basis=row.details.get("basis"),
                fields=row.details.get("fields", []) if row.reason == "numbers_edited" else [],
                record=LinkedRecordOut(**record.__dict__) if record is not None else None,
            )
        )
    return out


def _decision(request: Request, names: dict[int, str]) -> DecisionOut | None:
    if request.status in ("approved", "linked"):
        return DecisionOut(
            status="approved",
            by=names.get(request.approved_by) if request.approved_by is not None else None,
            at=request.approved_at,
            counts_commission=request.counts_commission,
            despite_warnings=request.approval_warnings or [],
        )
    if request.status == "rejected":
        return DecisionOut(
            status="rejected",
            by=names.get(request.rejected_by),
            at=request.rejected_at,
            reason=request.rejection_reason,
            label=rejection_reasons.label(request.rejection_reason, request.rejection_note),
        )
    return None


def to_file(db: Session, request: Request) -> RequestFileOut:
    names = _names(
        db,
        {request.approved_by, request.rejected_by} | {p.pinned_by for p in request.pins},
    )
    pending = request.status == "pending_review"
    return RequestFileOut(
        id=request.id,
        number_label=request.number_label,
        type=request.type,
        status=request.status,
        names={f: getattr(request, f) for f in NAME_FIELDS},
        names_reading={f: _reading(request, f) for f in NAME_FIELDS},
        full_name=request.full_name,
        national_id=request.national_id,
        family_number=request.family_number,
        birth_date=request.birth_date,
        issue_date=request.issue_date,
        expiry_date=request.expiry_date,
        birth_place=request.birth_place,
        issuing_authority=request.issuing_authority,
        images=[
            ImageOut(id=i.id, side=i.side)
            for i in sorted(request.images, key=lambda i: i.side, reverse=True)
        ],
        location=LocationOut(
            lat=request.location_lat,
            lng=request.location_lng,
            source=request.location_source,
            accuracy_m=request.location_accuracy_m,
        ),
        address=request.address,
        landmark=request.landmark,
        area_name=request.area_name,
        tower_code=request.tower_code,
        tower_name=request.tower_name,
        plan_name=request.plan_name,
        trial_price=request.trial_price,
        second_price=request.second_price,
        phone=request.phone,
        otp_verified_at=request.otp_verified_at,
        username=request.username,
        marketer_name=request.marketer.name,
        submitted_at=request.submitted_at,
        numbers=_numbers(request, names),
        reasons=_reasons(db, request),
        # A decided request is read-only: its confirmed warnings are in `decision`.
        warnings=live_check(db, request).warnings if pending else [],
        decision=_decision(request, names),
    )


# --- images (R9) ---------------------------------------------------------------------------------


def open_request_image(db: Session, user: User, image_id: uuid.UUID) -> Path:
    """The file of a request image for a review admin. Anyone else, a missing image and a missing
    file all get the same 404. Each successful open is written to image_access_log (§13)."""
    image = db.get(RequestImage, image_id)
    if image is None or not can_review(user):
        raise AppError("image_not_found", 404)
    path = image_store.open_path(image.file_name)
    if not path.is_file():
        log.error("request image file missing image=%s", image.id)
        raise AppError("image_not_found", 404)
    db.add(
        ImageAccessLog(
            user_id=user.id,
            image_id=image.id,
            request_id=image.request_id,
            draft_id=image.request.draft_id,
            side=image.side,
            purpose="view",
        )
    )
    db.commit()
    return path
