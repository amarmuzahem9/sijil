"""Append-only audit trail (Principle III). There are intentionally no update/delete helpers."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

# Any key containing one of these fragments is dropped from before/after…
_FORBIDDEN_FRAGMENTS = ("password", "token", "otp", "secret", "hash")
# …except these non-secret flags, which are explicitly allowed.
_ALLOWED_KEYS = frozenset({"must_change_password"})


def _clean(values: dict[str, Any] | None) -> dict[str, Any] | None:
    if values is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        lowered = key.lower()
        if lowered not in _ALLOWED_KEYS and any(f in lowered for f in _FORBIDDEN_FRAGMENTS):
            continue
        cleaned[key] = value.isoformat() if isinstance(value, datetime) else value
    return cleaned


def record(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=_clean(before),
        after=_clean(after),
    )
    db.add(entry)
    return entry
