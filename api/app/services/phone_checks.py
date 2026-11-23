"""Phone checks that run before an OTP code is sent (specs/007 research R9, specs/008 R10).

«الهاتف مستخدم» (docs/system.md §5.4 item 2, §6.1 row 1): when the normalized phone already
belongs to a subscriber (a pending, approved or linked request; later legacy and SAS records), no
code is sent and nothing counts toward the send limits. The refusal names no one (FR-007).
"""

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Draft
from app.services import match_service


def precheck_for_otp(db: Session, draft: Draft, phone: str) -> AppError | None:
    """None = the code may be sent; an AppError = refuse with that error (nothing is sent)."""
    del draft  # the phone alone decides; the draft's own record is never a subscriber
    if match_service.find_matches(db, phone=phone).phone:
        return AppError("phone_used", 409)
    return None
