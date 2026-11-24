"""The fixed reasons to undo «تم الربط» (docs/system.md v1.18 §6.5, specs/013 research R4).

Mirrored in web/src/lib/labels.ts. The codes match the `request_links_reason` check of migration
0016. No reason takes a free text, so no personal data can reach the notification or the audit
(owner, Q3).
"""

from app.errors import AppError

LABELS: dict[str, str] = {
    "not_linked_in_sas": "لم يُربط فعلياً في SAS",
    "by_mistake": "ضُغط بالخطأ",
    "other_request_linked": "ربط طلب آخر بدله",
    "other": "سبب آخر",
}


def validate(reason: str) -> None:
    """Raises AppError for a code outside the list."""
    if reason not in LABELS:
        raise AppError("validation_error", 422)
