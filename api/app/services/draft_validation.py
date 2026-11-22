"""Missing-items list of a draft (specs/005 data-model.md › "Validation rules", research.md R9).

Pure functions: a draft may be saved with any value within the length limits, and this list says
what is still missing or invalid, in page order. The client mirror is
web/src/lib/draftValidation.ts; both are tested against tests/fixtures/draft_validation_cases.json.
"""

from collections.abc import Iterable
from typing import Any, Protocol, TypedDict

from app.core.national_id import normalize_national_id
from app.core.phone import normalize_phone
from app.models.draft import NAME_FIELDS, OPTIONAL_NAME_FIELDS

# The seven required name fields (system.md §5.1 v1.5); each is its own missing item.
REQUIRED_NAME_FIELDS: tuple[str, ...] = tuple(
    name for name in NAME_FIELDS if name not in OPTIONAL_NAME_FIELDS
)

# Page order (FR-003): card images, card data, location, subscription, phone.
MISSING_ORDER: tuple[str, ...] = (
    "image_front",
    "image_back",
    *REQUIRED_NAME_FIELDS,
    "national_id",
    "family_number",
    "location",
    "address",
    "landmark",
    "area_id",
    "tower_id",
    "plan_id",
    "phone",
)


class MissingItem(TypedDict):
    field: str
    code: str


class DraftLike(Protocol):
    first_name: str | None
    father_name: str | None
    grandfather_name: str | None
    great_grandfather_name: str | None
    surname: str | None
    mother_first_name: str | None
    mother_second_name: str | None
    national_id: str | None
    family_number: str | None
    location_lat: float | None
    location_lng: float | None
    address: str | None
    landmark: str | None
    area_id: int | None
    tower_id: int | None
    plan_id: int | None
    phone_input: str | None


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def missing(draft: DraftLike, image_sides: Iterable[str]) -> list[MissingItem]:
    """Every empty or invalid item of `draft`, in MISSING_ORDER. Empty list = complete."""
    sides = set(image_sides)
    found: dict[str, str] = {}

    for side in ("front", "back"):
        if side not in sides:
            found[f"image_{side}"] = "required"

    for name in (*REQUIRED_NAME_FIELDS, "family_number", "address", "landmark"):
        if _blank(getattr(draft, name)):
            found[name] = "required"

    if _blank(draft.national_id):
        found["national_id"] = "required"
    elif normalize_national_id(draft.national_id) is None:
        found["national_id"] = "invalid_national_id"

    if draft.location_lat is None or draft.location_lng is None:
        found["location"] = "required"

    for name in ("area_id", "tower_id", "plan_id"):
        if getattr(draft, name) is None:
            found[name] = "required"

    if _blank(draft.phone_input):
        found["phone"] = "required"
    elif normalize_phone(draft.phone_input) is None:
        found["phone"] = "invalid_phone"

    return [{"field": f, "code": found[f]} for f in MISSING_ORDER if f in found]
