"""/api/drafts/* and /api/draft-images/* (specs/005 contracts/api.md).

Draft routes are marketer-only (`marketer_only`) and owner-checked in draft_service. The image
route (added with US2) also admits the main admin and `review` admins. Every draft call carries
`X-Client-Id`, one random UUID per page load of the form (research.md R3): it tells a save from
the same page apart from a save made on another device or another tab of the same session.
"""

import uuid

from fastapi import APIRouter, Header

from app.api.deps import AuthContext, require_roles
from app.errors import AppError

router = APIRouter(tags=["drafts"])

marketer_only = require_roles("marketer")


def _parse_client_id(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def client_id(x_client_id: str | None = Header(default=None)) -> uuid.UUID:
    """Required on writes: a missing or malformed value → 422 `validation_error`."""
    parsed = _parse_client_id(x_client_id)
    if parsed is None:
        raise AppError("validation_error", 422)
    return parsed


def optional_client_id(x_client_id: str | None = Header(default=None)) -> uuid.UUID | None:
    """For reads (GET, version poll): used only to compute `same_client`."""
    return _parse_client_id(x_client_id)


__all__ = ["AuthContext", "client_id", "marketer_only", "optional_client_id", "router"]
