"""Sign-in, session refresh and password change (contracts/api.md)."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.phone import normalize_phone
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    verify_password,
)
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import User, UserSession
from app.models.session import USER_AGENT_MAX
from app.services import audit_service

MIN_PASSWORD_LENGTH = 8


@dataclass
class AuthResult:
    user: User
    session: UserSession
    access_token: str
    refresh_token: str


def _new_session(db: Session, user: User, user_agent: str | None) -> tuple[UserSession, str]:
    now = utc_now()
    token = new_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(token),
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=get_settings().refresh_token_days),
        user_agent=user_agent[:USER_AGENT_MAX] if user_agent else None,
    )
    db.add(session)
    db.flush()
    return session, token


def _rotate(session: UserSession) -> str:
    """Issue a new refresh token for an existing session and slide its expiry."""
    now = utc_now()
    token = new_refresh_token()
    session.previous_token_hash = session.refresh_token_hash
    session.refresh_token_hash = hash_refresh_token(token)
    session.last_used_at = now
    session.expires_at = now + timedelta(days=get_settings().refresh_token_days)
    return token


def _result(user: User, session: UserSession, refresh_token: str) -> AuthResult:
    return AuthResult(user, session, create_access_token(user.id, session.id), refresh_token)


def login(db: Session, phone_raw: str, password: str, user_agent: str | None) -> AuthResult:
    phone = normalize_phone(phone_raw)
    if phone is None:
        raise AppError("invalid_phone", 422)

    user = db.execute(
        select(User).where(User.phone == phone).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        verify_password(DUMMY_HASH, password)  # same work as a real check (FR-005)
        raise AppError("invalid_credentials", 401)
    if not verify_password(user.password_hash, password):
        raise AppError("invalid_credentials", 401)
    if not user.is_active:
        raise AppError("account_inactive", 403)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_logins = 0
    session, token = _new_session(db, user, user_agent)
    db.commit()
    return _result(user, session, token)


def refresh(db: Session, refresh_token: str | None) -> AuthResult:
    if not refresh_token:
        raise AppError("session_revoked", 401)
    session = db.execute(
        select(UserSession)
        .where(UserSession.refresh_token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    ).scalar_one_or_none()
    if session is None or not session.is_valid(utc_now()):
        raise AppError("session_revoked", 401)
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AppError("account_inactive", 403)

    token = _rotate(session)
    db.commit()
    return _result(user, session, token)


def change_password(
    db: Session, user: User, session: UserSession, current: str, new: str
) -> AuthResult:
    if not verify_password(user.password_hash, current):
        raise AppError("wrong_current_password", 400)
    if len(new) < MIN_PASSWORD_LENGTH:
        raise AppError("weak_password", 422)
    if new == current:
        raise AppError("same_password", 422)

    was_forced = user.must_change_password
    now = utc_now()
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.updated_at = now

    # End every other device; this one keeps working with a rotated token.
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user.id,
            UserSession.id != session.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoke_reason="password_changed")
    )
    token = _rotate(session)
    audit_service.record(
        db,
        actor_id=user.id,
        action="user.password_changed",
        entity_type="user",
        entity_id=user.id,
        before={"must_change_password": was_forced},
        after={"must_change_password": False},
    )
    db.commit()
    return _result(user, session, token)
