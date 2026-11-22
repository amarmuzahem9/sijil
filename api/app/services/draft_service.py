"""Drafts of new-subscriber requests (specs/005 research.md R1–R4, R8).

This module is the base of the service: ownership, applying text/location/phone changes, and the
response shape. Saving with `version` (R3), images (R6), catalog copies (R4) and deletion (R8) are
added by their user stories.

Never log field values here: names, national IDs, family numbers and phones are sensitive
(FR-022, Principle II).
"""

import uuid
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.phone import normalize_phone
from app.errors import AppError
from app.models import Draft, DraftImage, User
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
from app.services import draft_validation

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
