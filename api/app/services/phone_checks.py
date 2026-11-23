"""Phone checks that run before an OTP code is sent (specs/007 research R9).

Feature 008 adds «الهاتف مستخدم» here (docs/system.md §5.4 item 2, §6.1): when the phone
already belongs to a request or subscriber, no code is sent. Until then every phone passes.
"""

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Draft


def precheck_for_otp(db: Session, draft: Draft, phone: str) -> AppError | None:
    """None = the code may be sent; an AppError = refuse with that error (nothing is sent)."""
    del db, draft, phone  # used by 008
    return None
