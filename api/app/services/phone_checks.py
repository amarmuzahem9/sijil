"""Phone checks that run before an OTP code is sent (specs/007 research R9, specs/008 R10,
specs/009 R6).

«الهاتف مستخدم» (docs/system.md §5.4 item 2, §6.1 row 1): when the normalized phone already
belongs to a subscriber (a pending, approved or linked request; later legacy and SAS records), no
code is sent and nothing counts toward the send limits. The refusal names no one (FR-007).

The one exception is a valid «طلب العودة للخدمة» choice: the code may go to a phone held only by
the records being brought back (specs/009 FR-007). A pending block is decided at submission.
"""

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Draft
from app.services import draft_service, match_service


def precheck_for_otp(db: Session, draft: Draft, phone: str) -> AppError | None:
    """None = the code may be sent; an AppError = refuse with that error (nothing is sent)."""
    holders = match_service.find_matches(db, phone=phone).phone_records
    if not holders:
        return None
    _, target, valid = draft_service.return_state(draft, draft_service.draft_matches(db, draft))
    in_target = {r.ref for r in target} if valid else set()
    if all(r.ref in in_target for r in holders):
        return None
    return AppError("phone_used", 409)
