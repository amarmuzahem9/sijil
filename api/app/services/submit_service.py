"""Submission: the authoritative check and decision (docs/system.md §6, §6.1 v1.9, §7.2, §7.3;
specs/008 research R6–R8, R13).

One transaction: refresh the catalog copies, check the missing items and the phone verification,
lock the phone, national ID and family keys, run the check engine, decide, and either refuse (the
draft stays; the attempt is audited) or create the request with the next number, move the images,
copy the readings, and remove the draft. A repeat for a submitted draft returns the same request.

Never log or audit the national ID, the family number, the full phone or names (Principle II).
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import (
    deletion_reasons,
    link_message,
    otp,
    rejection_reasons,
    request_search,
    request_status,
)
from app.core.decision import decide
from app.core.family_key import family_key
from app.core.matches import MatchRecord
from app.core.national_id import normalize_national_id
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import Draft, Request, RequestImage, RequestReason, User
from app.models.draft import NAME_FIELDS
from app.schemas.requests import RequestListItem, RequestOut
from app.services import audit_service, draft_service, match_service, otp_service
from app.services.numbers_edited import edited_fields

log = logging.getLogger("sijil.submit")

# Found at submission they refuse with their own code (409), not as a missing item (R6 step 7).
_REFUSAL_ITEMS = frozenset({"phone_used", "national_id_exists", "return_pending"})

_COPIED: tuple[str, ...] = (
    *NAME_FIELDS,
    "full_name",
    "no_surname",
    "family_number",
    "birth_date",
    "issue_date",
    "expiry_date",
    "birth_place",
    "issuing_authority",
    "national_id_check",
    "location_lat",
    "location_lng",
    "location_source",
    "location_accuracy_m",
    "address",
    "landmark",
    "area_id",
    "tower_id",
    "plan_id",
    "area_name",
    "tower_code",
    "tower_name",
    "plan_name",
    "trial_price",
    "second_price",
    "otp_verified_at",
)


def _lock(db: Session, key: str) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def _existing(db: Session, user: User, draft_id: uuid.UUID) -> Request | None:
    request = db.scalars(select(Request).where(Request.draft_id == draft_id)).one_or_none()
    if request is not None and request.marketer_id != user.id:
        raise AppError("draft_not_found", 404)
    return request


def _refuse(db: Session, user: User, draft_id: uuid.UUID, code: str) -> AppError:
    """Roll back everything, then audit the attempt on its own (Q2: the draft stays)."""
    db.rollback()
    audit_service.record(
        db,
        actor_id=user.id,
        action="request.submit_refused",
        entity_type="draft",
        entity_id=str(draft_id),
        after={"reason": code},
    )
    db.commit()
    log.info("submit draft=%s result=%s", draft_id, code)
    return AppError(code, 409)


def _card_readings(draft: Draft) -> dict:
    by_side = {reading.side: reading for reading in draft.card_readings}
    out: dict = {}
    for side in ("front", "back"):
        reading = by_side.get(side)
        out[side] = (
            None
            if reading is None
            else {
                "state": reading.state,
                "reason": reading.reason,
                "raw": reading.raw,
                "result": reading.result,
                "finished_at": reading.finished_at.isoformat() if reading.finished_at else None,
            }
        )
    return out


def submit(db: Session, user: User, draft_id: uuid.UUID, version: int) -> tuple[Request, bool]:
    """Returns (request, created). Raises AppError for every refusal (contracts/api.md)."""
    # 1. Already submitted (double tap, retry).
    existing = _existing(db, user, draft_id)
    if existing is not None:
        return existing, False

    # 2. The draft, locked; a concurrent submit of the same draft waits here.
    draft = db.get(Draft, draft_id, with_for_update=True)
    if draft is None:
        existing = _existing(db, user, draft_id)
        if existing is not None:
            return existing, False
        raise AppError("draft_not_found", 404)
    if draft.marketer_id != user.id:
        raise AppError("draft_not_found", 404)
    if draft.version != version:
        raise draft_service._conflict(db, draft, None)

    # 3. Final catalog copies; a price change also cancels the verification (007 R5).
    with db.no_autoflush:
        notices = draft_service.refresh_copies(db, draft)
        otp_service.clear_if_changed(draft)
    if notices:
        db.commit()  # keep the cleared choice, as a save would
        raise AppError("catalog_changed", 409, extra={"notices": [n.model_dump() for n in notices]})

    # 4. Missing items, including an unconfirmed family match.
    checks = draft_service.draft_checks(db, draft)
    # Rows 1 and 2 come before row 3: a used phone or a known national ID refuses on its own
    # code, even if the family is not confirmed (§6.1 note 1).
    skip = set(_REFUSAL_ITEMS)
    if checks.phone_used or checks.national_id_exists:
        skip.add("family_exists_unconfirmed")
    missing = [
        item for item in draft_service.missing_items(draft, checks) if item["field"] not in skip
    ]
    if missing:
        _keep_refreshed(db, draft)
        raise AppError("draft_incomplete", 422, extra={"missing": missing})

    # 5. The verification must match the current phone, tower, category and prices.
    if not otp_service.is_verified(draft):
        _keep_refreshed(db, draft)
        raise AppError("otp_needs_reverify", 409)

    # 6. Lock the keys in a fixed order, then look again (SC-004).
    phone = draft.phone_normalized
    national_id = normalize_national_id(draft.national_id)
    key = family_key(draft.family_number)
    _lock(db, f"match:phone:{phone}")
    _lock(db, f"match:nid:{national_id}")
    _lock(db, f"match:family:{key}")
    matches = match_service.find_matches(db, phone=phone, national_id=national_id, family_key=key)

    # 7. Decide (§6.1 in order).
    edited = edited_fields(draft)
    # A return choice counts only if its target still exists under the locks (specs/009 R7);
    # a stale one falls back to the rules for a new request.
    _, target, return_valid = draft_service.return_state(draft, matches)
    decision = decide(
        matches,
        edited,
        additional_confirmed=draft.additional_confirmed_key == key,
        return_valid=return_valid,
    )
    if decision.refusal in _REFUSAL_ITEMS:
        raise _refuse(db, user, draft_id, decision.refusal)
    if decision.refusal is not None:  # an unconfirmed family; step 4 already covers it
        raise AppError("draft_incomplete", 422, extra={"missing": []})

    request_status.check(None, decision.status)
    now = utc_now()
    number = db.execute(text("SELECT nextval('request_number_seq')")).scalar_one()
    request = Request(
        number=number,
        draft_id=draft.id,
        marketer_id=user.id,
        type=decision.type,
        status=decision.status,
        **{field: getattr(draft, field) for field in _COPIED},
        national_id=national_id,
        national_id_input=draft.national_id,
        family_key=key,
        # The marketer's values as submitted; a review pin never changes them (specs/010 R4).
        submitted_national_id=draft.national_id,
        submitted_family_number=draft.family_number,
        card_fields=dict(draft.card_fields or {}),
        card_readings=_card_readings(draft),
        phone=phone,
        username=_username(db, draft, phone, target if decision.type == "return" else []),
        submitted_at=now,
        approved_at=now if decision.status == "approved" else None,
        approved_by=None,
        created_at=now,
        updated_at=now,
    )
    db.add(request)
    db.flush()
    for reason in decision.reasons:
        if reason.matches:
            for match in reason.matches:
                db.add(
                    RequestReason(
                        request_id=request.id,
                        reason=reason.reason,
                        matched_source=match.source,
                        matched_ref=match.ref_id,
                        details={"basis": reason.basis} if reason.basis else {},
                    )
                )
        else:
            db.add(
                RequestReason(
                    request_id=request.id, reason=reason.reason, details={"fields": reason.fields}
                )
            )
    for image in draft.images:
        db.add(
            RequestImage(
                id=image.id,
                request_id=request.id,
                side=image.side,
                file_name=image.file_name,
                size_bytes=image.size_bytes,
                width=image.width,
                height=image.height,
                uploaded_by=image.uploaded_by,
                created_at=image.created_at,
            )
        )
    # The draft's image and reading rows go with it (cascade); the files stay for the request.
    db.delete(draft)
    audit_service.record(
        db,
        actor_id=user.id,
        action="request.submitted",
        entity_type="request",
        entity_id=str(number),
        after={
            "number": number,
            "type": request.type,
            "status": request.status,
            "reasons": reason_codes(decision.reasons),
            "tower_code": request.tower_code,
            "plan_name": request.plan_name,
        },
    )
    db.commit()
    db.refresh(request)
    log.info(
        "submit draft=%s result=%s number=%s phone=%s",
        draft_id,
        decision.result,
        number,
        otp.mask_phone(phone),
    )
    return request, True


def _username(db: Session, draft: Draft, phone: str, target: list[MatchRecord]) -> str:
    """§8.2, or for a return the historical username of the newest target record that has one
    (specs/009 FR-015, research R7). Only Sijil records carry a username in 009."""
    ids = [int(r.ref_id) for r in target if r.source == "sijil"]
    if ids:
        historical = db.scalars(
            select(Request.username)
            .where(Request.id.in_(ids))
            .order_by(Request.submitted_at.desc(), Request.id.desc())
            .limit(1)
        ).first()
        if historical:
            return historical
    return f"{draft.tower_code}-{phone}"


def _keep_refreshed(db: Session, draft: Draft) -> None:
    """A refusal after step 3 keeps what a save would have kept (refreshed prices, a cancelled
    verification). Nothing changed → the commit writes nothing and the version stays."""
    del draft
    db.commit()


def reason_codes(reasons) -> list[str]:
    codes: list[str] = []
    for reason in reasons:
        if reason.reason not in codes:
            codes.append(reason.reason)
    return codes


# --- reading -----------------------------------------------------------------------------------


def _result(request: Request) -> str:
    if request.status != "pending_review":
        return request.status
    codes = {r.reason for r in request.reasons}
    if "return" in codes:
        return "pending_approval"
    if "family_exists" in codes:
        return "pending_family"
    if "numbers_conflict" in codes:
        return "pending_approval"
    return "pending_review"


def _rejection_label(request: Request) -> str | None:
    """A deleted request lost the note: the reason's name only (specs/011 R11)."""
    if request.is_deleted and request.rejection_reason is not None:
        return rejection_reasons.LABELS[request.rejection_reason]
    return rejection_reasons.label(request.rejection_reason, request.rejection_note)


def _deleted_out(request: Request) -> RequestOut:
    """«محذوف»: the kept fields and the reason only (specs/011 contracts/api.md › marketer)."""
    return RequestOut(
        id=request.id,
        number=request.number,
        number_label=request.number_label,
        type=request.type,
        status=request.status,
        reasons=[],
        full_name=None,
        tower_code=request.tower_code,
        tower_name=request.tower_name,
        area_name=None,
        plan_name=None,
        trial_price=None,
        second_price=None,
        phone=None,
        address=None,
        landmark=None,
        marketer_name=None,
        username=None,
        submitted_at=request.submitted_at,
        approved_at=None,
        result="deleted",
        deleted_at=request.deleted_at,
        deletion_label=deletion_reasons.LABELS[request.deletion_reason],
    )


def to_out(request: Request) -> RequestOut:
    if request.is_deleted:
        return _deleted_out(request)
    return RequestOut(
        id=request.id,
        number=request.number,
        number_label=request.number_label,
        type=request.type,
        status=request.status,
        reasons=reason_codes(request.reasons),
        full_name=request.full_name,
        tower_code=request.tower_code,
        tower_name=request.tower_name,
        area_name=request.area_name,
        plan_name=request.plan_name,
        trial_price=request.trial_price,
        second_price=request.second_price,
        phone=request.phone,
        address=request.address,
        landmark=request.landmark,
        marketer_name=request.marketer.name,
        username=request.username if request.status in ("approved", "linked") else None,
        submitted_at=request.submitted_at,
        approved_at=request.approved_at,
        result=_result(request),
        rejection_reason=request.rejection_reason,
        rejection_label=_rejection_label(request),
        rejected_at=request.rejected_at,
        link_message=link_message.compose(request),
        linked_at=request.linked_at,
    )


def get_own(db: Session, user: User, request_id: int) -> Request:
    request = db.get(Request, request_id)
    if request is None or request.marketer_id != user.id:
        raise AppError("request_not_found", 404)
    return request


def _search(query, text: str):
    """Narrow `query` by the search box (specs/012 R8). A deleted request has no name or phone
    left, so only its number finds it (FR-014)."""
    if len(text.strip()) < request_search.MIN_LENGTH:
        raise AppError("validation_error", 422)
    term = request_search.classify(text)
    if term is None:
        return query.where(False)
    if term.kind == "number":
        return query.where(Request.number == term.value)
    if term.kind == "phone":
        return query.where(Request.phone == term.value)
    return query.where(Request.full_name.contains(term.value, autoescape=True))


def list_own(
    db: Session, user: User, statuses: list[str] | None = None, q: str | None = None
) -> list[RequestListItem]:
    query = select(Request).where(Request.marketer_id == user.id)
    if statuses:
        query = query.where(Request.status.in_(statuses))
    if q is not None:
        query = _search(query, q)
    # The «تم الربط» tab goes by link time, newest first (specs/013 FR-017); the rest by submission.
    if statuses == ["linked"] and q is None:
        order = (Request.linked_at.desc(), Request.id.desc())
    else:
        order = (Request.submitted_at.desc(), Request.id.desc())
    rows = db.scalars(query.order_by(*order)).all()
    return [
        RequestListItem(
            id=r.id,
            number_label=r.number_label,
            full_name=r.full_name,
            status=r.status,
            type=r.type,
            submitted_at=r.submitted_at,
            tower_code=r.tower_code,
            tower_name=r.tower_name,
            rejection_label=_rejection_label(r),
            deleted_at=r.deleted_at,
            deletion_label=(
                deletion_reasons.LABELS[r.deletion_reason] if r.deletion_reason else None
            ),
            linked_at=r.linked_at,
        )
        for r in rows
    ]
