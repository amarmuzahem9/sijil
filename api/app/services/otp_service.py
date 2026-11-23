"""Phone verification by WhatsApp OTP — docs/system.md §5.4, §8.3; specs/007 research R3–R10.

- `send`: normalize the stored phone, run the 008 pre-send check, then take the draft and phone
  locks and check the 60 s wait and the hourly limit. Then call the sender, and only after it
  accepts, insert the challenge (a failed send leaves no row and counts for nothing, R6).
- `verify`: check the newest challenge of the draft (active, same context, not expired, fewer
  than 3 wrong attempts) and, on the right code, mark the draft verified.
- `clear_if_changed`: called on every draft save; a change of phone, tower, category or prices
  cancels the verification for good (R5).
- `status`: the `otp` block of DraftOut.

The plain code lives only in this module's local variables during `send` and in the WhatsApp
message. It is never returned, logged, or stored.
"""

import logging
import math
import uuid
from datetime import datetime, timedelta

from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session, object_session

from app.config import get_settings
from app.core import otp
from app.core.phone import normalize_phone
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import Draft, OtpChallenge, User
from app.schemas.drafts import OtpStatusOut
from app.services import settings_service
from app.services.otp_sender import OtpSender, OtpSendError, get_otp_sender
from app.services.phone_checks import precheck_for_otp

log = logging.getLogger("sijil.otp")

_SEND_ERRORS = {
    "not_configured": ("otp_not_configured", 503),
    "no_credit": ("otp_no_credit", 502),
    "rejected": ("otp_rejected", 502),
    "unavailable": ("otp_unavailable", 502),
}


def context_hash(draft: Draft) -> str:
    """The one fingerprint used at send, verify, every save, and by 008 at submission (R4)."""
    return otp.context_hash(
        phone=draft.phone_normalized,
        tower_id=draft.tower_id,
        plan_id=draft.plan_id,
        trial_price=draft.trial_price,
        second_price=draft.second_price,
    )


def is_verified(draft: Draft) -> bool:
    return draft.otp_verified_at is not None and draft.otp_context_hash == context_hash(draft)


def clear_if_changed(draft: Draft) -> None:
    """On save: a verification whose context changed is cancelled (values put back stay
    cancelled, spec US2 scenario 5)."""
    if draft.otp_verified_at is not None and draft.otp_context_hash != context_hash(draft):
        draft.otp_verified_at = None
        draft.otp_context_hash = None


# --- reading --------------------------------------------------------------------------------


def _newest(db: Session, draft_id: uuid.UUID, *, lock: bool = False) -> OtpChallenge | None:
    query = (
        select(OtpChallenge)
        .where(OtpChallenge.request_id == draft_id)
        .order_by(OtpChallenge.created_at.desc(), OtpChallenge.id)
        .limit(1)
    )
    if lock:
        query = query.with_for_update()
    return db.execute(query).scalar_one_or_none()


def _is_active(challenge: OtpChallenge, current_context: str, now: datetime) -> bool:
    return (
        challenge.verified_at is None
        and challenge.attempts < otp.MAX_ATTEMPTS
        and now < challenge.expires_at
        and challenge.context_hash == current_context
    )


def _resend_at(challenge: OtpChallenge | None, now: datetime) -> datetime | None:
    if challenge is None:
        return None
    at = challenge.created_at + otp.RESEND_WAIT
    return at if at > now else None


def status(draft: Draft) -> OtpStatusOut:
    db = object_session(draft)
    if db is None:
        return OtpStatusOut()
    if is_verified(draft):
        return OtpStatusOut(status="verified", verified_at=draft.otp_verified_at)
    now = utc_now()
    newest = _newest(db, draft.id)
    resend_at = _resend_at(newest, now)
    if newest is not None and _is_active(newest, context_hash(draft), now):
        return OtpStatusOut(
            status="sent",
            phone=newest.phone,
            resend_at=resend_at,
            expires_at=newest.expires_at,
            attempts_left=otp.MAX_ATTEMPTS - newest.attempts,
        )
    was_verified = db.execute(
        select(
            exists().where(
                OtpChallenge.request_id == draft.id, OtpChallenge.verified_at.is_not(None)
            )
        )
    ).scalar_one()
    return OtpStatusOut(status="needs_reverify" if was_verified else "none", resend_at=resend_at)


# --- sending --------------------------------------------------------------------------------


def _owned(db: Session, user: User, draft_id: uuid.UUID, *, lock: bool = False) -> Draft:
    draft = db.get(Draft, draft_id, with_for_update=lock)
    if draft is None or draft.marketer_id != user.id:
        raise AppError("draft_not_found", 404)
    return draft


def _lock(db: Session, key: str) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def _minutes_until(moment: datetime, now: datetime) -> int:
    return max(1, math.ceil((moment - now).total_seconds() / 60))


def _check_limits(db: Session, draft: Draft, phone: str, now: datetime) -> None:
    resend_at = _resend_at(_newest(db, draft.id), now)
    if resend_at is not None:
        seconds = max(1, math.ceil((resend_at - now).total_seconds()))
        raise AppError(
            "otp_resend_wait",
            429,
            message=f"إعادة الإرسال بعد {seconds} ثانية",
            extra={"retry_after_s": seconds},
        )
    recent = (
        db.execute(
            select(OtpChallenge.created_at)
            .where(
                OtpChallenge.phone == phone,
                OtpChallenge.created_at > now - otp.HOURLY_WINDOW,
            )
            .order_by(OtpChallenge.created_at)
        )
        .scalars()
        .all()
    )
    if len(recent) >= otp.HOURLY_MAX:
        minutes = _minutes_until(recent[0] + otp.HOURLY_WINDOW, now)
        raise AppError(
            "otp_hourly_limit",
            429,
            message=(
                f"وصلت الحد الأقصى ({otp.HOURLY_MAX} رموز في الساعة) لهذا الرقم، "
                f"حاول بعد {minutes} دقيقة"
            ),
            extra={"retry_after_min": minutes},
        )


def _send_error(err: OtpSendError) -> AppError:
    if err.reason == "busy":
        if err.wait_minutes:
            return AppError(
                "otp_provider_busy",
                429,
                message=f"حاول بعد {err.wait_minutes} دقيقة",
                extra={"retry_after_min": err.wait_minutes},
            )
        return AppError("otp_provider_busy", 429)
    code, http_status = _SEND_ERRORS[err.reason]
    return AppError(code, http_status)


def send(db: Session, user: User, draft_id: uuid.UUID, sender: OtpSender | None = None) -> Draft:
    draft = _owned(db, user, draft_id)
    phone = normalize_phone(draft.phone_input)
    if phone is None:
        raise AppError("invalid_phone", 422)
    if is_verified(draft):
        raise AppError("otp_already_verified", 409)
    refusal = precheck_for_otp(db, draft, phone)
    if refusal is not None:
        raise refusal

    # Held until commit/rollback; the draft row itself stays unlocked so autosave keeps working.
    _lock(db, f"otp:draft:{draft.id}")
    _lock(db, f"otp:phone:{phone}")
    now = utc_now()
    _check_limits(db, draft, phone, now)

    settings = get_settings()
    minutes = settings_service.get_general(db)[settings_service.OTP_MINUTES_KEY]
    challenge_id = uuid.uuid4()
    code = otp.generate_code(settings.otp_fake_code)
    try:
        receipt = (sender or get_otp_sender()).send(phone, code)
    except OtpSendError as err:
        db.rollback()  # nothing inserted; releases the locks
        log.warning(
            "otp send draft=%s phone=%s result=%s", draft_id, otp.mask_phone(phone), err.reason
        )
        raise _send_error(err) from None

    db.add(
        OtpChallenge(
            id=challenge_id,
            request_id=draft.id,
            phone=phone,
            code_hash=otp.code_hash(challenge_id, code),
            context_hash=context_hash(draft),
            expires_at=now + timedelta(minutes=minutes),
            attempts=0,
            created_at=now,
        )
    )
    del code
    db.commit()
    log.info(
        "otp send draft=%s phone=%s result=ok provider_id=%s cost=%s",
        draft_id,
        otp.mask_phone(phone),
        receipt.provider_id,
        receipt.cost,
    )
    return draft


# --- checking -------------------------------------------------------------------------------


def _wrong_message(attempts_left: int) -> str:
    left = "بقيت محاولتان" if attempts_left == 2 else "بقيت محاولة واحدة"
    return f"الرمز غير صحيح، {left}"


def verify(
    db: Session, user: User, client_id: uuid.UUID, draft_id: uuid.UUID, raw_code: str
) -> Draft:
    # The draft row is locked so a concurrent autosave cannot race the versioned UPDATE.
    draft = _owned(db, user, draft_id, lock=True)
    code = otp.normalize_code_entry(raw_code)
    if code is None:
        raise AppError("otp_code_format", 422)
    challenge = _newest(db, draft.id, lock=True)
    now = utc_now()
    if (
        challenge is None
        or challenge.verified_at is not None
        or challenge.context_hash != context_hash(draft)
    ):
        raise AppError("otp_no_active", 409)
    if challenge.attempts >= otp.MAX_ATTEMPTS:
        raise AppError("otp_cancelled", 410)
    if now >= challenge.expires_at:
        raise AppError("otp_expired", 410)

    if not otp.verify_code_hash(challenge.id, code, challenge.code_hash):
        challenge.attempts += 1
        attempts_left = otp.MAX_ATTEMPTS - challenge.attempts
        db.commit()
        log.info("otp verify draft=%s result=wrong left=%s", draft_id, attempts_left)
        if attempts_left <= 0:
            raise AppError("otp_cancelled", 410)
        raise AppError(
            "otp_wrong",
            422,
            message=_wrong_message(attempts_left),
            extra={"attempts_left": attempts_left},
        )

    challenge.verified_at = now
    draft.otp_verified_at = now
    draft.otp_context_hash = challenge.context_hash
    draft.updated_at = now
    draft.last_client_id = client_id
    db.commit()
    log.info("otp verify draft=%s result=ok", draft_id)
    return draft
