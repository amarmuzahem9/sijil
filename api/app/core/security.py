"""Password hashing (Argon2id), access tokens (JWT) and refresh tokens (opaque, hashed)."""

import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings
from app.core.timeutil import utc_now

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


class TokenExpired(Exception):
    pass


class TokenInvalid(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Verified against when the phone has no account, so response timing does not reveal it (FR-005).
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def create_access_token(user_id: int, session_id: uuid.UUID) -> str:
    settings = get_settings()
    now = utc_now()
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> tuple[int, uuid.UUID]:
    """Return (user_id, session_id). Expiry is checked against the app clock, not the OS clock."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[_ALGORITHM],
            options={"verify_exp": False, "verify_iat": False, "require": ["sub", "sid", "exp"]},
        )
        if payload.get("typ") != "access":
            raise TokenInvalid
        user_id = int(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
        exp = int(payload["exp"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise TokenInvalid from exc
    if utc_now().timestamp() >= exp:
        raise TokenExpired
    return user_id, session_id


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
