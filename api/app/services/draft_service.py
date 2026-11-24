"""Drafts of new-subscriber requests (specs/005 research.md R1–R4, R8).

This module is the base of the service: ownership, applying text/location/phone changes, and the
response shape. Saving with `version` (R3), images (R6), catalog copies (R4) and deletion (R8) are
added by their user stories.

Never log field values here: names, national IDs, family numbers and phones are sensitive
(FR-022, Principle II).
"""

import logging
import uuid
from collections.abc import Iterable
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.access import has_any_permission
from app.core.arabic_name import (
    InvalidArabicName,
    clean_arabic_name,
    clean_place_text,
    join_full_name,
)
from app.core.card_reading import AUTHORITY_MAX, BIRTH_PLACE_MAX
from app.core.family_key import family_key
from app.core.iraq_bounds import in_iraq
from app.core.matches import Matches, MatchRecord, ReturnBasis
from app.core.national_id import normalize_national_id
from app.core.phone import normalize_phone, to_latin_digits
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import Area, Draft, DraftImage, ImageAccessLog, Plan, Tower, User
from app.models.draft import CARD_FIELDS, FULL_NAME_FIELDS, NAME_FIELDS, TEXT_LIMITS
from app.schemas.drafts import (
    DraftChanges,
    DraftChecksOut,
    DraftImages,
    DraftListItem,
    DraftOut,
    ImageOut,
    LocationOut,
    MissingOut,
    NoticeOut,
)
from app.services import (
    audit_service,
    card_reading_service,
    draft_validation,
    image_store,
    match_service,
    otp_service,
)

log = logging.getLogger("sijil.drafts")

# Plain text columns set straight from DraftChanges (after trimming).
TEXT_FIELDS: tuple[str, ...] = (
    "national_id",
    "family_number",
    "address",
    "landmark",
    "phone_input",
)


def get_owned(db: Session, user: User, draft_id: uuid.UUID, *, lock: bool = False) -> Draft:
    """The caller's own draft. A missing draft and another marketer's draft look the same (404),
    so a draft's existence is never revealed (contracts/api.md)."""
    draft = db.get(Draft, draft_id, with_for_update=lock)
    if draft is None or draft.marketer_id != user.id:
        raise AppError("draft_not_found", 404)
    return draft


def clean_text(field: str, value: str | None) -> str | None:
    """Trim; empty becomes None; longer than the data-model limit → 422 `too_long` with `field`."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > TEXT_LIMITS[field]:
        raise AppError("too_long", 422, extra={"field": field})
    return cleaned


def clean_name(field: str, value: str | None) -> str | None:
    """A name field (research.md R12): Arabic letters and single spaces, ≤ 50 characters.
    A digit or a non-Arabic letter → 422 `invalid_name_text` with `field`; nothing is saved."""
    try:
        cleaned = clean_arabic_name(value)
    except InvalidArabicName:
        raise AppError("invalid_name_text", 422, extra={"field": field}) from None
    if cleaned is not None and len(cleaned) > TEXT_LIMITS[field]:
        raise AppError("too_long", 422, extra={"field": field})
    return cleaned


def apply_changes(draft: Draft, changes: DraftChanges) -> None:
    """Apply the name, text, location and phone keys present in `changes` (omitted keys are
    unchanged, `None` clears). Subscription ids are handled by the catalog-copy step (R4).
    `full_name` is recomputed here on every change of a name (R12)."""
    given = changes.model_fields_set
    before = {field: getattr(draft, field) for field in CARD_FIELDS}

    names = {f: clean_name(f, getattr(changes, f)) for f in NAME_FIELDS if f in given}
    for field, value in names.items():
        setattr(draft, field, value)

    for field in TEXT_FIELDS:
        if field in given:
            setattr(draft, field, clean_text(field, getattr(changes, field)))

    # Back of the card (owner change, system.md v1.8).
    for field in ("birth_date", "issue_date", "expiry_date"):
        if field in given:
            setattr(draft, field, getattr(changes, field))
    if "birth_place" in given:
        try:
            place = clean_place_text(changes.birth_place)
        except InvalidArabicName:
            raise AppError("invalid_place_text", 422, extra={"field": "birth_place"}) from None
        if place is not None and len(place) > BIRTH_PLACE_MAX:
            raise AppError("too_long", 422, extra={"field": "birth_place"})
        draft.birth_place = place
    if "issuing_authority" in given:
        authority = (changes.issuing_authority or "").strip() or None
        if authority is not None and len(authority) > AUTHORITY_MAX:
            raise AppError("too_long", 422, extra={"field": "issuing_authority"})
        draft.issuing_authority = authority

    # «لا يوجد لقب على البطاقة» (specs/006 research R9): typing a surname clears the choice;
    # choosing it empties the surname.
    if draft.surname:
        draft.no_surname = False
    if "no_surname" in given and changes.no_surname is not None:
        draft.no_surname = changes.no_surname
        if changes.no_surname:
            draft.surname = None
    if names or "no_surname" in given:
        draft.full_name = join_full_name([getattr(draft, f) for f in FULL_NAME_FIELDS])

    # National ID against the verified MRZ (research R7): any change drops the confirmation;
    # «اعتماد هذا الرقم» confirms the current value.
    check = draft.national_id_check
    if check and check.get("mrz"):
        confirmed = check.get("confirmed_value")
        if draft.national_id != before["national_id"]:
            confirmed = None
        if changes.national_id_confirmed and draft.national_id:
            confirmed = draft.national_id
        if confirmed != check.get("confirmed_value"):
            draft.national_id_check = {**check, "confirmed_value": confirmed}

    # A card field changed by the marketer is «عُدِّل يدوياً» from now on (research R8); the
    # original reading stays. Echoes of the same value (e.g. a resent save) change nothing.
    edited = [f for f in CARD_FIELDS if getattr(draft, f) != before[f]]
    if edited:
        marks = dict(draft.card_fields or {})
        for field in edited:
            mark = dict(marks.get(field) or {"original": None, "confidence": None, "from": None})
            mark["source"] = "edited"
            marks[field] = mark
        draft.card_fields = marks  # reassign: in-place JSONB changes are not tracked

    if "phone_input" in given:
        # Set only when §8.1 normalization succeeds; the CHECK in migration 0005 backs this up.
        draft.phone_normalized = normalize_phone(draft.phone_input)

    if "location" in given:
        loc = changes.location
        if loc is not None and not in_iraq(loc.lat, loc.lng):
            # §5.2 v1.6: every pin, whatever its source, must be inside Iraq's bounding box.
            raise AppError("location_outside_iraq", 422, extra={"field": "location"})
        draft.location_lat = loc.lat if loc else None
        draft.location_lng = loc.lng if loc else None
        draft.location_source = loc.source if loc else None
        draft.location_accuracy_m = loc.accuracy_m if loc else None


def image_sides(images: Iterable[DraftImage]) -> list[str]:
    return [image.side for image in images]


# --- early checks (specs/008 research R5, R12) ------------------------------------------------


def draft_matches(db: Session, draft: Draft) -> Matches:
    """Every record holding the draft's phone, national ID or family number (research R1)."""
    return match_service.find_matches(
        db,
        phone=draft.phone_normalized,
        national_id=normalize_national_id(draft.national_id),
        family_key=family_key(draft.family_number),
    )


def return_key_for(draft: Draft, basis: ReturnBasis | None) -> str | None:
    """The key a return choice is stored under (research R3); None when the draft lacks it."""
    if basis == "identity":
        national_id = normalize_national_id(draft.national_id)
        key = family_key(draft.family_number)
        return f"identity:{national_id}:{key}" if national_id and key else None
    if basis == "phone":
        return f"phone:{draft.phone_normalized}" if draft.phone_normalized else None
    return None


def return_state(
    draft: Draft, found: Matches
) -> tuple[ReturnBasis | None, list[MatchRecord], bool]:
    """(basis, target, valid): the choice counts only while the draft's values still give the
    stored key and the target is not empty. A changed number or phone makes it stale."""
    basis, target = found.return_target()
    key = return_key_for(draft, basis)
    valid = bool(target) and key is not None and draft.return_key == key
    return basis, target, valid


def draft_checks(db: Session, draft: Draft) -> DraftChecksOut:
    """Does the draft's phone, national ID or family number already belong to a subscriber?
    Booleans and the return basis only; the page never learns who (FR-007, FR-012)."""
    found = draft_matches(db, draft)
    basis, target, chosen = return_state(draft, found)
    in_target = {r.ref for r in target} if chosen else set()

    def outside(records: list[MatchRecord]) -> bool:
        return any(r.ref not in in_target for r in records)

    key = family_key(draft.family_number)
    # v1.10 (specs/009 research R1): "national ID exists" means the same person (national ID and
    # family number on one record); the family path is for records that are not that person.
    family = outside(found.family_only)
    return DraftChecksOut(
        phone_used=outside(found.phone_records),
        national_id_exists=bool(found.same_person),
        id_conflict=outside(found.id_conflict),
        family_exists=family,
        additional_confirmed=family and key is not None and draft.additional_confirmed_key == key,
        return_available=bool(target),
        return_basis=basis,
        return_chosen=chosen,
        return_pending=chosen and any(r.pending for r in target),
    )


def apply_confirmation(db: Session, draft: Draft, changes: DraftChanges) -> None:
    """«إضافة اشتراك ثاني» (research R12): `true` stores the current family key, only while that
    family matches an existing subscriber; `false` withdraws it. A later change of the family
    number makes the stored key stale, so the confirmation drops without extra code. It excludes
    a return choice (specs/009 research R3)."""
    if "additional_confirmed" not in changes.model_fields_set:
        return
    if not changes.additional_confirmed:
        draft.additional_confirmed_key = None
        return
    key = family_key(draft.family_number)
    if key is None or not _family_only(db, draft, key):
        raise AppError("no_family_match", 422)
    draft.additional_confirmed_key = key
    draft.return_key = None


def _family_only(db: Session, draft: Draft, key: str) -> bool:
    """A family match that is not the same person (rule 3), judged with the draft's national ID."""
    found = match_service.find_matches(
        db, national_id=normalize_national_id(draft.national_id), family_key=key
    )
    return bool(found.family_only)


def apply_return_choice(db: Session, user: User, draft: Draft, changes: DraftChanges) -> None:
    """«طلب العودة للخدمة» (specs/009 research R3). `true` stores the key of the current return
    target (identity preferred over phone) and drops the second-subscription confirmation;
    `false` withdraws it. Both are audited with the draft id and the basis only (R11). Without
    the key in `changes`, a stale stored key is cleared quietly."""
    if "return_chosen" not in changes.model_fields_set:
        if draft.return_key is not None and not return_state(draft, draft_matches(db, draft))[2]:
            draft.return_key = None
        return
    if changes.return_chosen:
        basis, target = draft_matches(db, draft).return_target()
        key = return_key_for(draft, basis)
        if not target or key is None:
            raise AppError("no_return_match", 422)
        draft.return_key = key
        draft.additional_confirmed_key = None
        action, after = "draft.return_chosen", {"basis": basis}
    else:
        if draft.return_key is None:
            return
        draft.return_key = None
        action, after = "draft.return_withdrawn", {}
    audit_service.record(
        db,
        actor_id=user.id,
        action=action,
        entity_type="draft",
        entity_id=str(draft.id),
        after=after,
    )


# The 005/006 page order with the 008 and 009 items, which need the database (research R5).
_AFTER = {
    "national_id_unconfirmed": ("national_id_exists", "return_pending"),
    "family_number": ("family_exists_unconfirmed",),
    "phone": ("phone_used",),
}
MISSING_ORDER: tuple[str, ...] = tuple(
    f for base in draft_validation.MISSING_ORDER for f in (base, *_AFTER.get(base, ()))
)
_ORDER = {f: i for i, f in enumerate(MISSING_ORDER)}


def missing_items(
    draft: Draft, checks: DraftChecksOut | None = None
) -> list[draft_validation.MissingItem]:
    """The 005/006 list plus the database items, in page order (MISSING_ORDER). A valid return
    choice replaces the same-person and family items; a pending record blocks it (009 R5)."""
    items = draft_validation.missing(draft, image_sides(draft.images))
    if checks is None:
        return items
    extra = []
    if checks.national_id_exists and not checks.return_chosen:
        extra.append({"field": "national_id_exists", "code": "national_id_exists"})
    if checks.return_pending:
        extra.append({"field": "return_pending", "code": "return_pending"})
    if checks.family_exists and not checks.additional_confirmed and not checks.return_chosen:
        extra.append({"field": "family_exists_unconfirmed", "code": "family_exists_unconfirmed"})
    if checks.phone_used:
        extra.append({"field": "phone_used", "code": "phone_used"})
    return sorted([*items, *extra], key=lambda item: _ORDER[item["field"]])


def to_out(db: Session, draft: Draft, notices: list[NoticeOut] | None = None) -> DraftOut:
    by_side = {image.side: image for image in draft.images}
    checks = draft_checks(db, draft)

    def image_out(side: str) -> ImageOut | None:
        image = by_side.get(side)
        if image is None:
            return None
        return ImageOut(
            id=image.id,
            size_bytes=image.size_bytes,
            width=image.width,
            height=image.height,
            created_at=image.created_at,
        )

    location = None
    if draft.location_lat is not None and draft.location_lng is not None:
        location = LocationOut(
            lat=draft.location_lat,
            lng=draft.location_lng,
            source=draft.location_source,
            accuracy_m=draft.location_accuracy_m,
        )

    return DraftOut(
        id=draft.id,
        status=draft.status,
        version=draft.version,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        **{field: getattr(draft, field) for field in NAME_FIELDS},
        full_name=draft.full_name,
        national_id=draft.national_id,
        family_number=draft.family_number,
        location=location,
        address=draft.address,
        landmark=draft.landmark,
        area_id=draft.area_id,
        tower_id=draft.tower_id,
        plan_id=draft.plan_id,
        area_name=draft.area_name,
        tower_code=draft.tower_code,
        plan_name=draft.plan_name,
        trial_price=draft.trial_price,
        second_price=draft.second_price,
        phone_input=draft.phone_input,
        phone_normalized=draft.phone_normalized,
        birth_date=draft.birth_date,
        birth_place=draft.birth_place,
        issue_date=draft.issue_date,
        expiry_date=draft.expiry_date,
        issuing_authority=draft.issuing_authority,
        images=DraftImages(front=image_out("front"), back=image_out("back")),
        no_surname=draft.no_surname,
        card_fields=card_reading_service.card_fields_out(draft),
        national_id_check=card_reading_service.national_id_check_out(draft),
        card_reading=card_reading_service.reading_out(draft),
        missing=[MissingOut(**item) for item in missing_items(draft, checks)],
        notices=notices or [],
        otp=otp_service.status(draft),
        checks=checks,
    )


# --- saving with version (US1, research.md R1, R3) ---------------------------------------------


def _touch(draft: Draft, client_id: uuid.UUID) -> None:
    """Mark a save: always dirty, so the ORM issues the versioned UPDATE even for a no-op."""
    draft.updated_at = utc_now()
    draft.last_client_id = client_id


def _conflict(db: Session, draft: Draft, client_id: uuid.UUID | None) -> AppError:
    db.rollback()
    db.refresh(draft)
    return AppError(
        "draft_conflict",
        409,
        extra={
            "version": draft.version,
            "updated_at": draft.updated_at.isoformat(),
            "same_client": client_id is not None and draft.last_client_id == client_id,
        },
    )


def create_if_absent(
    db: Session, user: User, client_id: uuid.UUID, draft_id: uuid.UUID, changes: DraftChanges
) -> tuple[Draft, list[NoticeOut], bool]:
    """PUT: create the draft with the client's UUID, or return the caller's existing draft
    unchanged (an idempotent retry). Returns (draft, notices, created)."""
    existing = db.get(Draft, draft_id)
    if existing is not None:
        if existing.marketer_id != user.id:
            raise AppError("draft_not_found", 404)
        return existing, compute_notices(db, existing), False

    draft = Draft(id=draft_id, marketer_id=user.id, last_client_id=client_id)
    apply_changes(draft, changes)
    apply_confirmation(db, draft, changes)
    apply_return_choice(db, user, draft, changes)
    apply_subscription(db, draft, changes)
    notices = refresh_copies(db, draft)
    try:
        with db.begin_nested():
            db.add(draft)
            db.flush()
    except IntegrityError:
        # Two concurrent PUTs with the same id: the other one won.
        db.expunge(draft)
        existing = db.get(Draft, draft_id)
        if existing is None or existing.marketer_id != user.id:
            raise AppError("draft_not_found", 404) from None
        return existing, compute_notices(db, existing), False
    db.commit()
    return draft, notices, True


def patch(
    db: Session,
    user: User,
    client_id: uuid.UUID,
    draft_id: uuid.UUID,
    version: int,
    changes: DraftChanges,
) -> tuple[Draft, list[NoticeOut]]:
    """Apply a partial change if `version` is current; otherwise 409 `draft_conflict` with the
    current version and whether the newer save came from this same page (`same_client`).
    Every save also refreshes the catalog copies (research.md R4)."""
    draft = get_owned(db, user, draft_id)
    if draft.version != version:
        raise _conflict(db, draft, client_id)
    # Catalog reads must not autoflush the half-updated draft: each flush of a dirty draft is a
    # versioned UPDATE, and one save must bump the version exactly once.
    with db.no_autoflush:
        apply_changes(draft, changes)
        apply_confirmation(db, draft, changes)
        apply_return_choice(db, user, draft, changes)
        apply_subscription(db, draft, changes)
        notices = refresh_copies(db, draft)
        # A change of phone, tower, category or prices cancels the OTP verification (specs/007 R5).
        otp_service.clear_if_changed(draft)
    _touch(draft, client_id)
    try:
        db.flush()  # UPDATE ... WHERE id = :id AND version = :version (version_id_col)
    except StaleDataError:
        raise _conflict(db, draft, client_id) from None
    db.commit()
    return draft, notices


# --- card images (US2, research.md R6, R7) -------------------------------------------------------


def save_image(
    db: Session,
    user: User,
    client_id: uuid.UUID,
    draft_id: uuid.UUID,
    side: str,
    upload: UploadFile,
) -> Draft:
    """Store one card side, replacing any previous image of that side, and bump the version.

    The row is locked so a concurrent PATCH cannot interleave. The new file is written before the
    commit and removed if the commit fails; the replaced file is removed after the commit.
    """
    draft = get_owned(db, user, draft_id, lock=True)
    stored = image_store.save_upload(upload)
    # The side's card reading now belongs to the new image (specs/006 research R5).
    existing = next((image for image in draft.images if image.side == side), None)
    replaced = existing.file_name if existing else None
    try:
        if existing is None:
            draft.images.append(
                DraftImage(
                    side=side,
                    file_name=stored.file_name,
                    size_bytes=stored.size_bytes,
                    width=stored.width,
                    height=stored.height,
                    uploaded_by=user.id,
                )
            )
        else:
            existing.file_name = stored.file_name
            existing.size_bytes = stored.size_bytes
            existing.width = stored.width
            existing.height = stored.height
            existing.uploaded_by = user.id
            existing.created_at = utc_now()
        card_reading_service.mark_pending(draft, side, stored.file_name, client_id)
        _touch(draft, client_id)
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        image_store.unlink_quietly(stored.file_name)
        raise
    if replaced:
        image_store.unlink_quietly(replaced)
    db.refresh(draft)
    return draft


def open_image(db: Session, user: User, image_id: uuid.UUID) -> tuple[DraftImage, Path]:
    """The image file if `user` may see it: the owner, the main admin, or a `review` admin
    (FR-002). Everyone else gets the same 404 as for a missing image. Each successful open is
    written to image_access_log (§13, Principle II)."""
    image = db.get(DraftImage, image_id)
    if image is None:
        raise AppError("image_not_found", 404)
    draft = image.draft
    allowed = draft.marketer_id == user.id or has_any_permission(
        user.role, user.permissions, ["review"]
    )
    if not allowed:
        raise AppError("image_not_found", 404)
    path = image_store.open_path(image.file_name)
    if not path.is_file():
        log.error("image file missing for image %s", image.id)
        raise AppError("image_not_found", 404)
    db.add(ImageAccessLog(user_id=user.id, image_id=image.id, draft_id=draft.id, side=image.side))
    db.commit()
    return image, path


# --- subscription choice and catalog copies (US7, research.md R2, R4) ----------------------------

_SUBSCRIPTION_KEYS = ("area_id", "tower_id", "plan_id")


def _unavailable(field: str) -> NoticeOut:
    return NoticeOut(field=field, code="choice_unavailable")


def apply_subscription(db: Session, draft: Draft, changes: DraftChanges) -> None:
    """Set the chosen ids from `changes`. An id that does not exist → 422 `invalid_choice`.
    Changing the area clears the tower unless the same change sets a tower."""
    given = changes.model_fields_set
    models = {"area_id": Area, "tower_id": Tower, "plan_id": Plan}
    for key in _SUBSCRIPTION_KEYS:
        if key not in given:
            continue
        value = getattr(changes, key)
        if value is not None and db.get(models[key], value) is None:
            raise AppError("invalid_choice", 422, extra={"field": key})
    if "area_id" in given and changes.area_id != draft.area_id and "tower_id" not in given:
        draft.tower_id = None
    for key in _SUBSCRIPTION_KEYS:
        if key in given:
            setattr(draft, key, getattr(changes, key))


def _check_choices(
    db: Session, draft: Draft
) -> tuple[Area | None, Tower | None, Plan | None, list[NoticeOut]]:
    """The currently valid choices and a notice for every chosen-but-unavailable one.

    An id that became null by ON DELETE SET NULL while its copy remains also counts as
    unavailable (the admin deleted an unused item).
    """
    notices: list[NoticeOut] = []

    area = db.get(Area, draft.area_id) if draft.area_id is not None else None
    if area is not None and not area.is_active:
        area = None
    if area is None and (draft.area_id is not None or draft.area_name is not None):
        notices.append(_unavailable("area_id"))

    tower = db.get(Tower, draft.tower_id) if draft.tower_id is not None else None
    if tower is not None and (not tower.is_active or area is None or tower.area_id != area.id):
        tower = None
    if tower is None and (draft.tower_id is not None or draft.tower_code is not None):
        notices.append(_unavailable("tower_id"))

    plan = db.get(Plan, draft.plan_id) if draft.plan_id is not None else None
    if plan is not None and not plan.is_active:
        plan = None
    if plan is None and (draft.plan_id is not None or draft.plan_name is not None):
        notices.append(_unavailable("plan_id"))
    return area, tower, plan, notices


def refresh_copies(db: Session, draft: Draft) -> list[NoticeOut]:
    """On every save: clear unavailable choices and copy names and prices from the current
    catalog (data-model.md › "Copies"; the final copies are taken at submission, feature 008)."""
    area, tower, plan, notices = _check_choices(db, draft)
    draft.area_id = area.id if area else None
    draft.area_name = area.name if area else None
    draft.tower_id = tower.id if tower else None
    draft.tower_code = tower.code if tower else None
    draft.tower_name = tower.name if tower else None
    draft.plan_id = plan.id if plan else None
    draft.plan_name = plan.name if plan else None
    draft.trial_price = plan.trial_price if plan else None
    draft.second_price = plan.second_price if plan else None
    return notices


def compute_notices(db: Session, draft: Draft) -> list[NoticeOut]:
    """Read-only (GET): what the next save would change. Renames refresh silently."""
    _, _, plan, notices = _check_choices(db, draft)
    if plan is not None and (draft.trial_price, draft.second_price) != (
        plan.trial_price,
        plan.second_price,
    ):
        notices.append(
            NoticeOut(
                field="plan_id",
                code="price_changed",
                old={"trial_price": draft.trial_price, "second_price": draft.second_price},
                new={"trial_price": plan.trial_price, "second_price": plan.second_price},
            )
        )
    return notices


# --- drafts list and deletion (US4, research.md R8) ----------------------------------------------


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_own(db: Session, user: User, q: str | None = None) -> list[DraftListItem]:
    """The caller's drafts, newest change first; `q` matches the name or the phone digits."""
    stmt = select(Draft).where(Draft.marketer_id == user.id)
    text = (q or "").strip()
    if text:
        conditions = [Draft.full_name.ilike(f"%{_like_escape(text)}%", escape="\\")]
        digits = "".join(c for c in to_latin_digits(text) if c.isascii() and c.isdigit())
        if digits:
            conditions.append(Draft.phone_normalized.like(f"%{digits}%"))
        stmt = stmt.where(or_(*conditions))
    drafts = db.scalars(stmt.order_by(Draft.updated_at.desc())).all()
    return [
        DraftListItem(
            id=d.id,
            full_name=d.full_name,
            tower_code=d.tower_code,
            phone_normalized=d.phone_normalized,
            updated_at=d.updated_at,
            missing_count=len(missing_items(d, draft_checks(db, d))),
            has_images=bool(d.images),
        )
        for d in drafts
    ]


def delete(db: Session, user: User, draft_id: uuid.UUID) -> None:
    """Delete an unsubmitted draft with its images (system.md §5 v1.4, constitution 1.1.1).

    Rows and the audit entry are committed first, then the files are removed: a failed commit
    leaves the files in place, and a file left behind by a crash is removed by `prune-uploads`.
    The audit entry carries no card data, names, phone or file names (FR-019, Principle II).
    """
    draft = get_owned(db, user, draft_id, lock=True)
    file_names = [image.file_name for image in draft.images]
    before = {
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
        "tower_code": draft.tower_code,
        "image_count": len(file_names),
        "missing_count": len(draft_validation.missing(draft, image_sides(draft.images))),
    }
    db.delete(draft)
    audit_service.record(
        db,
        actor_id=user.id,
        action="draft.deleted",
        entity_type="draft",
        entity_id=str(draft_id),
        before=before,
    )
    db.commit()
    for name in file_names:
        image_store.unlink_quietly(name)


def referenced_file_names(db: Session) -> set[str]:
    """Files still in use: draft images, submitted requests' images (008), legacy subscribers'
    images and the staged images of open legacy previews (specs/014 research R9)."""
    from app.models import LegacyImage, RequestImage
    from app.services.legacy_import_service import staged_file_names

    drafts = set(db.scalars(select(DraftImage.file_name)).all())
    requests = set(db.scalars(select(RequestImage.file_name)).all())
    legacy = set(db.scalars(select(LegacyImage.file_name)).all())
    return drafts | requests | legacy | staged_file_names(db)
