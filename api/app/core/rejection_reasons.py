"""The fixed rejection reasons (docs/system.md v1.14 §6.4, specs/010 research R6).

Mirrored in web/src/lib/labels.ts. The codes match the database check of migration 0013.
`other` («سبب آخر») needs the admin's own note (3 to 300 characters after trimming); every other
code takes no note, so the marketer sees exactly the fixed label.
"""

from app.errors import AppError

LABELS: dict[str, str] = {
    "card_unclear": "صورة البطاقة غير واضحة",
    "numbers_mismatch": "الأرقام غير مطابقة للبطاقة",
    "under_15_days": "المتبقي من الاشتراك الأول أقل من 15 يوماً",
    "active_subscription": "المشترك لديه اشتراك فعّال",
    "other": "سبب آخر",
}

NOTE_MIN = 3
NOTE_MAX = 300


def validate(reason: str, note: str | None) -> str | None:
    """The note to store (trimmed), or None. Raises AppError for an invalid pair."""
    if reason not in LABELS:
        raise AppError("validation_error", 422)
    cleaned = (note or "").strip()
    if reason != "other":
        if cleaned:
            raise AppError("validation_error", 422)
        return None
    if len(cleaned) < NOTE_MIN:
        raise AppError("rejection_note_required", 422)
    if len(cleaned) > NOTE_MAX:
        raise AppError("validation_error", 422)
    return cleaned


def label(reason: str | None, note: str | None) -> str | None:
    """What the marketer sees: the fixed label, or the admin's note for «سبب آخر»."""
    if reason is None:
        return None
    if reason == "other":
        return note
    return LABELS[reason]
