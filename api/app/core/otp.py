"""OTP rules — docs/system.md §8.3; specs/007 research.md R3, R4, R7.

Pure functions: code generation, keyed code hashing, the context fingerprint, code-entry
normalization and phone masking for logs. Nothing here logs or stores a code.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from functools import lru_cache

from app.config import get_settings
from app.core.phone import to_latin_digits

CODE_LENGTH = 6
RESEND_WAIT = timedelta(seconds=60)
HOURLY_WINDOW = timedelta(minutes=60)
HOURLY_MAX = 5
MAX_ATTEMPTS = 3

_CODE_KEY_LABEL = b"sijil/otp-code/v1"
_CONTEXT_VERSION = "v1"


def generate_code(fixed: str = "") -> str:
    """A uniformly random 6-digit code, or `fixed` (OTP_FAKE_CODE, fake mode only)."""
    if fixed:
        return fixed
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


@lru_cache
def _code_key(secret: str) -> bytes:
    return hmac.new(secret.encode(), _CODE_KEY_LABEL, hashlib.sha256).digest()


def code_hash(challenge_id: uuid.UUID, code: str) -> str:
    """HMAC-SHA256 of `<challenge id>:<code>` with a key derived from JWT_SECRET (R3)."""
    key = _code_key(get_settings().jwt_secret)
    return hmac.new(key, f"{challenge_id}:{code}".encode(), hashlib.sha256).hexdigest()


def verify_code_hash(challenge_id: uuid.UUID, code: str, stored: str) -> bool:
    return hmac.compare_digest(code_hash(challenge_id, code), stored)


def context_hash(
    *,
    phone: str | None,
    tower_id: int | None,
    plan_id: int | None,
    trial_price: int | None,
    second_price: int | None,
) -> str:
    """SHA-256 fingerprint of what a verification belongs to (R4). Not keyed: the values are not
    secret, and rotating JWT_SECRET must not drop verifications."""
    parts = [_CONTEXT_VERSION] + [
        "" if v is None else str(v) for v in (phone, tower_id, plan_id, trial_price, second_price)
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def normalize_code_entry(raw: str | None) -> str | None:
    """Arabic-Indic digits → ASCII, spaces removed; exactly 6 ASCII digits or None."""
    if raw is None:
        return None
    text = "".join(to_latin_digits(raw).split())
    if len(text) == CODE_LENGTH and text.isascii() and text.isdigit():
        return text
    return None


def mask_phone(phone: str | None) -> str:
    """`07801234567` → `0780****567` for log lines (R10)."""
    if not phone:
        return "-"
    if len(phone) < 8:
        return "*" * len(phone)
    return f"{phone[:4]}{'*' * (len(phone) - 7)}{phone[-3:]}"


def to_international(phone: str) -> str:
    """Normalized `07XXXXXXXXX` → `9647XXXXXXXXX` (OTPIQ format, digits without `+`)."""
    return "964" + phone[1:]
