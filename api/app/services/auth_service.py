"""Sign-in, session refresh and password change (contracts/api.md)."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

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
# Two tabs of the same browser may refresh at the same instant with the same cookie; the second
# one presents the just-rotated token. Within this window that is not treated as theft.
REUSE_GRACE = timedelta(seconds=30)


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


def _minutes_ar(minutes: int) -> str:
    if minutes <= 1:
        return "دقيقة واحدة"
    if minutes == 2:
        return "دقيقتين"
    if minutes <= 10:
        return f"{minutes} دقائق"
    return f"{minutes} دقيقة"


def _locked_error(locked_until: datetime) -> AppError:
    seconds = max(1, math.ceil((locked_until - utc_now()).total_seconds()))
    minutes = math.ceil(seconds / 60)
    return AppError(
        "account_locked",
        423,
        message=f"تم إيقاف الدخول مؤقتاً بسبب محاولات خاطئة متكررة، حاول بعد {_minutes_ar(minutes)}",
        headers={"Retry-After": str(seconds)},
        extra={"retry_after_seconds": seconds},
    )


def login(db: Session, phone_raw: str, password: str, user_agent: str | None) -> AuthResult:
    phone = normalize_phone(phone_raw)
    if phone is None:
        raise AppError("invalid_phone", 422)  # not counted against any account

    # Row lock: concurrent attempts for one account are serialized (lockout counter is exact).
    user = db.execute(
        select(User).where(User.phone == phone).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        verify_password(DUMMY_HASH, password)  # same work as a real check (FR-005)
        raise AppError("invalid_credentials", 401)

    now = utc_now()
    if user.locked_until is not None and now < user.locked_until:
        db.commit()  # release the row lock
        raise _locked_error(user.locked_until)  # even with the correct password (FR-006)

    if not verify_password(user.password_hash, password):
        _register_failure(db, user, now)  # commits
        if user.locked_until is not None and now < user.locked_until:
            raise _locked_error(user.locked_until)
        raise AppError("invalid_credentials", 401)
    if not user.is_active:
        db.commit()
        raise AppError("account_inactive", 403)

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.failed_logins = 0
    user.locked_until = None
    session, token = _new_session(db, user, user_agent)
    db.commit()
    return _result(user, session, token)


def _register_failure(db: Session, user: User, now: datetime) -> None:
    """data-model.md "Lockout state": the Nth consecutive failure locks the account."""
    settings = get_settings()
    user.failed_logins += 1
    if user.failed_logins >= settings.lockout_threshold:
        user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
        user.failed_logins = 0
        audit_service.record(
            db,
            actor_id=None,
            action="user.locked",
            entity_type="user",
            entity_id=user.id,
            after={"locked_until": user.locked_until},
        )
    db.commit()


def refresh(db: Session, refresh_token: str | None) -> AuthResult:
    if not refresh_token:
        raise AppError("session_revoked", 401)
    now = utc_now()
    token_hash = hash_refresh_token(refresh_token)
    session = db.execute(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash).with_for_update()
    ).scalar_one_or_none()

    if session is None:
        # Not the current token: is it the one replaced by the last rotation?
        rotated = db.execute(
            select(UserSession)
            .where(UserSession.previous_token_hash == token_hash)
            .with_for_update()
        ).scalar_one_or_none()
        if rotated is None or not rotated.is_valid(now):
            raise AppError("session_revoked", 401)
        if now - rotated.last_used_at > REUSE_GRACE:
            # A token that was already exchanged is being replayed: assume theft, end the session.
            rotated.revoked_at = now
            rotated.revoke_reason = "reuse_detected"
            db.commit()
            raise AppError("session_revoked", 401)
        # Within the grace window: a second tab refreshed at the same moment. Rotate normally.
        session = rotated

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AppError("account_inactive", 403)  # before validity: deactivation revokes too
    if not session.is_valid(now):
        raise AppError("session_revoked", 401)

    token = _rotate(session)
    db.commit()
    return _result(user, session, token)


def logout(db: Session, refresh_token: str | None) -> None:
    """End only this device's session (FR-009). Silent when there is nothing to end."""
    if not refresh_token:
        return
    token_hash = hash_refresh_token(refresh_token)
    session = db.execute(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash).with_for_update()
    ).scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = utc_now()
        session.revoke_reason = "logout"
        db.commit()


def deactivate_user_sessions(db: Session, user_id: int, reason: str) -> int:
    """Revoke every open session of a user (feature 002: deactivation and password reset).

    The caller commits, so this happens in the same transaction as the account change.
    """
    result = db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utc_now(), revoke_reason=reason)
    )
    return result.rowcount or 0


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
