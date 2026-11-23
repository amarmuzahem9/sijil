"""The fixed deletion reasons (docs/system.md v1.15 §7.4, specs/011 data-model.md).

Mirrored in web/src/lib/labels.ts. The codes match the database check of migration 0014. No
reason takes a free text, so no personal data can reach the mark or the audit (owner, Q1).
"""

from app.errors import AppError

LABELS: dict[str, str] = {
    "duplicate": "طلب مكرر",
    "test": "طلب تجريبي",
    "entry_error": "خطأ إدخال",
    "other": "سبب آخر",
}


def validate(reason: str) -> None:
    """Raises AppError for a code outside the list."""
    if reason not in LABELS:
        raise AppError("validation_error", 422)
