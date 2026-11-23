"""«حذف مشترك»: erase a pending or rejected request in place (docs/system.md v1.15 §7.4,
constitution III v1.3.0; specs/011 research R1 to R5, R12).

The row stays with its number, marketer, status, dates, tower, plan, prices and the rejection
reason's name, plus the deletion mark. Every personal column becomes NULL, the image rows, pins
and the request's own OTP rows are removed in the same transaction, and the image files are
unlinked after the commit (a file left by a crash has no row any more, so `prune-uploads` removes
it). The audit entry and the log carry the number, the reason and counts only (Principle II).
"""

import logging

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import deletion_reasons, request_number
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import Request, RequestImage, RequestNumberPin, User
from app.models.otp import OtpChallenge
from app.models.request import DELETABLE_STATUSES, ERASED_COLUMNS
from app.schemas.admin_requests import DeleteIn
from app.services import audit_service, image_store
from app.services.review_service import can_delete, can_review

log = logging.getLogger("sijil.deletion")


def _locked(db: Session, user: User, request_id: int) -> Request:
    """The row under `FOR UPDATE`, the same lock accept, reject and pin take (R3), then the
    checks in the order of contracts/api.md."""
    request = db.scalars(
        select(Request)
        .where(Request.id == request_id)
        .with_for_update(of=Request)
        .execution_options(populate_existing=True)
    ).one_or_none()
    if request is None or not can_review(user):
        raise AppError("request_not_found", 404)
    if not can_delete(user):
        raise AppError("forbidden", 403)
    if request.is_deleted:
        raise AppError("request_deleted", 409)
    if request.status not in DELETABLE_STATUSES:
        raise AppError("request_not_deletable", 409, extra={"status": request.status})
    return request


def delete(db: Session, user: User, request_id: int, body: DeleteIn) -> Request:
    request = _locked(db, user, request_id)
    deletion_reasons.validate(body.reason)
    if request_number.parse(body.confirm_number) != request.number:
        raise AppError("number_mismatch", 422)

    images = [(image.id, image.file_name) for image in request.images]
    before = {
        "status": request.status,
        "image_count": len(images),
        "pin_count": len(request.pins),
    }
    phone = request.phone

    # R4: the rows go with the erasure; R5: the OTP rows of submitted or deleted drafts only, so
    # another marketer's running verification of the same phone is kept.
    db.execute(sql_delete(RequestImage).where(RequestImage.request_id == request.id))
    db.execute(sql_delete(RequestNumberPin).where(RequestNumberPin.request_id == request.id))
    db.execute(
        sql_delete(OtpChallenge).where(
            OtpChallenge.phone == phone, OtpChallenge.request_id.is_(None)
        )
    )
    # R1: one UPDATE erases every personal column and sets the mark (`requests_erasure`).
    for column in ERASED_COLUMNS:
        setattr(request, column, None)
    request.deleted_at = utc_now()
    request.deleted_by = user.id
    request.deletion_reason = body.reason
    request.updated_at = request.deleted_at

    audit_service.record(
        db,
        actor_id=user.id,
        action="request.deleted",
        entity_type="request",
        entity_id=str(request.number),
        before=before,
        after={"deleted": True, "reason": body.reason},
    )
    db.commit()
    db.expire(request, ["images", "pins"])

    for image_id, file_name in images:
        if not image_store.open_path(file_name).is_file():
            log.warning("deleted request image file missing image=%s", image_id)
        image_store.unlink_quietly(file_name)
    log.info("request deleted number=%s reason=%s", request.number, body.reason)
    return request
