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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.access import has_any_permission
from app.core.phone import normalize_phone
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import Draft, DraftImage, ImageAccessLog, User
from app.models.draft import TEXT_LIMITS
from app.schemas.drafts import (
    DraftChanges,
    DraftImages,
    DraftOut,
    ImageOut,
    LocationOut,
    MissingOut,
    NoticeOut,
)
from app.services import draft_validation, image_store

log = logging.getLogger("sijil.drafts")

# Plain text columns set straight from DraftChanges (after trimming).
TEXT_FIELDS: tuple[str, ...] = (
    "subscriber_name",
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


def apply_changes(draft: Draft, changes: DraftChanges) -> None:
    """Apply the text, location and phone keys present in `changes` (omitted keys are unchanged,
    `None` clears). Subscription ids are handled by the catalog-copy step (research.md R4)."""
    given = changes.model_fields_set

    for field in TEXT_FIELDS:
        if field in given:
            setattr(draft, field, clean_text(field, getattr(changes, field)))

    if "phone_input" in given:
        # Set only when §8.1 normalization succeeds; the CHECK in migration 0005 backs this up.
        draft.phone_normalized = normalize_phone(draft.phone_input)

    if "location" in given:
        loc = changes.location
        draft.location_lat = loc.lat if loc else None
        draft.location_lng = loc.lng if loc else None
        draft.location_source = loc.source if loc else None
        draft.location_accuracy_m = loc.accuracy_m if loc else None


def image_sides(images: Iterable[DraftImage]) -> list[str]:
    return [image.side for image in images]


def to_out(draft: Draft, notices: list[NoticeOut] | None = None) -> DraftOut:
    by_side = {image.side: image for image in draft.images}

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
        subscriber_name=draft.subscriber_name,
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
        images=DraftImages(front=image_out("front"), back=image_out("back")),
        missing=[
            MissingOut(**item)
            for item in draft_validation.missing(draft, image_sides(draft.images))
        ],
        notices=notices or [],
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
) -> tuple[Draft, bool]:
    """PUT: create the draft with the client's UUID, or return the caller's existing draft
    unchanged (an idempotent retry). Returns (draft, created)."""
    existing = db.get(Draft, draft_id)
    if existing is not None:
        if existing.marketer_id != user.id:
            raise AppError("draft_not_found", 404)
        return existing, False

    draft = Draft(id=draft_id, marketer_id=user.id, last_client_id=client_id)
    apply_changes(draft, changes)
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
        return existing, False
    db.commit()
    return draft, True


def patch(
    db: Session,
    user: User,
    client_id: uuid.UUID,
    draft_id: uuid.UUID,
    version: int,
    changes: DraftChanges,
) -> Draft:
    """Apply a partial change if `version` is current; otherwise 409 `draft_conflict` with the
    current version and whether the newer save came from this same page (`same_client`)."""
    draft = get_owned(db, user, draft_id)
    if draft.version != version:
        raise _conflict(db, draft, client_id)
    apply_changes(draft, changes)
    _touch(draft, client_id)
    try:
        db.flush()  # UPDATE ... WHERE id = :id AND version = :version (version_id_col)
    except StaleDataError:
        raise _conflict(db, draft, client_id) from None
    db.commit()
    return draft


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
