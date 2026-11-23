"""Row 4 of §6.1: were the national ID or the family number changed from the card?
(docs/system.md §6.1 v1.9, specs/008 research R4, FR-005a.)

Decided by value, not by the «عُدِّل يدوياً» mark: the final value is compared, with the §6.2 keys,
to what the card gave (the reading's `original`, and for the national ID a verified MRZ too).
Equal to one of them → not edited. Different, or the card gave nothing (typed by hand) → edited.
"""

from typing import Any, Protocol

from app.core.family_key import family_key
from app.core.national_id import normalize_national_id

FIELDS = ("national_id", "family_number")


class _DraftLike(Protocol):
    national_id: str | None
    family_number: str | None
    card_fields: dict[str, Any]
    national_id_check: dict[str, Any] | None


def _card_values(draft: _DraftLike, name: str) -> list[str | None]:
    values = [((draft.card_fields or {}).get(name) or {}).get("original")]
    if name == "national_id":
        values.append((draft.national_id_check or {}).get("mrz"))
    return values


def edited_fields(draft: _DraftLike) -> list[str]:
    edited: list[str] = []
    for name in FIELDS:
        key = normalize_national_id if name == "national_id" else family_key
        final = key(getattr(draft, name))
        read = {key(v) for v in _card_values(draft, name) if v}
        read.discard(None)
        if final is None or final not in read:
            edited.append(name)
    return edited
