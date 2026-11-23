"""Admin review test helpers (specs/010 tasks). Synthetic data only."""

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.timeutil import utc_now
from app.models import Request, RequestReason, User
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory


def admin_with(make_user, *permissions: str, name: str | None = None) -> User:
    """An added admin holding exactly `permissions`."""
    user = make_user("admin", name=name)
    user.permissions = list(permissions)
    return user


def headers_for(client, user: User) -> dict[str, str]:
    return auth_header(login(client, user.phone))


def pending_request(
    db: Session,
    marketer: User,
    reasons: list[tuple[str, Request | None, dict[str, Any]]],
    *,
    minutes_ago: int = 0,
    **overrides: Any,
) -> Request:
    """A pending request with the given reason rows: (reason, matched sijil request or None,
    details). `minutes_ago` orders submissions."""
    when = utc_now() - timedelta(minutes=minutes_ago)
    request = request_factory(
        db,
        marketer,
        status="pending_review",
        submitted_at=when,
        otp_verified_at=when,
        **overrides,
    )
    for reason, matched, details in reasons:
        db.add(
            RequestReason(
                request_id=request.id,
                reason=reason,
                matched_source="sijil" if matched is not None else None,
                matched_ref=str(matched.id) if matched is not None else None,
                details=details,
            )
        )
    db.flush()
    db.expire(request, ["reasons"])
    return request
