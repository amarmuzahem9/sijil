"""Authentication and authorization dependencies (Principle IX: every route declares one)."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenExpired, TokenInvalid, decode_access_token
from app.core.timeutil import utc_now
from app.db import get_db
from app.errors import AppError
from app.models import User, UserSession

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    session: UserSession


def current_user_allow_password_change(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthContext:
    """Valid, active session — even if the user still has to change the password."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise AppError("not_authenticated", 401)
    try:
        user_id, session_id = decode_access_token(creds.credentials)
    except TokenExpired as exc:
        raise AppError("token_expired", 401) from exc
    except TokenInvalid as exc:
        raise AppError("not_authenticated", 401) from exc

    # Checked on every request so sign-out and deactivation take effect immediately (FR-007).
    row = db.execute(
        select(User, UserSession)
        .join(UserSession, UserSession.user_id == User.id)
        .where(User.id == user_id, UserSession.id == session_id)
    ).first()
    if row is None:
        raise AppError("session_revoked", 401)
    user, session = row
    if not session.is_valid(utc_now()):
        raise AppError("session_revoked", 401)
    if not user.is_active:
        raise AppError("account_inactive", 403)
    return AuthContext(user, session)


def current_user(ctx: AuthContext = Depends(current_user_allow_password_change)) -> AuthContext:
    """Valid session and no pending forced password change (FR-011)."""
    if ctx.user.must_change_password:
        raise AppError("password_change_required", 403)
    return ctx


def require_roles(*roles: str) -> Callable[..., AuthContext]:
    def dependency(ctx: AuthContext = Depends(current_user)) -> AuthContext:
        if ctx.user.role not in roles:
            raise AppError("forbidden", 403)
        return ctx

    return dependency
