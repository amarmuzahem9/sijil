"""/api/admin/requests/* and /api/admin/request-images/* — admin review (specs/010
contracts/api.md).

Every route needs the main admin or an admin with `review`, checked on the server (Principle IX).
The list answers 403 to anyone else; a single request or image answers 404, so its existence does
not leak.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, current_user, require_permission
from app.db import get_db
from app.schemas.admin_requests import (
    AcceptIn,
    ByNumberOut,
    DeleteIn,
    PendingList,
    PinIn,
    RejectIn,
    RequestFileOut,
)
from app.services import deletion_service, review_service

router = APIRouter(prefix="/admin", tags=["admin-review"])

review_only = require_permission("review")

ReasonFilter = Literal["family_exists", "return", "numbers_edited", "numbers_conflict"]


@router.get("/requests/pending", response_model=PendingList)
def list_pending(
    reason: ReasonFilter | None = Query(default=None),
    _: AuthContext = Depends(review_only),
    db: Session = Depends(get_db),
) -> PendingList:
    """Oldest first; `reason` keeps requests holding that reason (not «لم يعد ينطبق»)."""
    return review_service.list_pending(db, reason)


@router.get("/requests/by-number/{text}", response_model=ByNumberOut)
def find_by_number(
    text: str,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> ByNumberOut:
    """«فتح طلب برقمه»: «T3C-1005», «1005» or «١٠٠٥»; any status. 404 «لا يوجد طلب بهذا الرقم»
    for an unknown number and for a caller without `review` (specs/011 R8)."""
    return ByNumberOut(id=review_service.find_by_number(db, ctx.user, text))


@router.get("/requests/{request_id}", response_model=RequestFileOut)
def get_request_file(
    request_id: int,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequestFileOut:
    """404 for a caller without `review`, the same as for a missing request."""
    return review_service.to_file(
        db, review_service.get_for_review(db, ctx.user, request_id), ctx.user
    )


@router.post("/requests/{request_id}/accept", response_model=RequestFileOut)
def accept_request(
    request_id: int,
    body: AcceptIn,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequestFileOut:
    """«قبول». A return needs `counts_commission`; warnings need `confirm_warnings` (R7)."""
    request = review_service.accept(db, ctx.user, request_id, body)
    return review_service.to_file(db, request, ctx.user)


@router.post("/requests/{request_id}/reject", response_model=RequestFileOut)
def reject_request(
    request_id: int,
    body: RejectIn,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequestFileOut:
    """«رفض» with a fixed reason, or «سبب آخر» with the admin's note (R6)."""
    request = review_service.reject(db, ctx.user, request_id, body)
    return review_service.to_file(db, request, ctx.user)


@router.post("/requests/{request_id}/pin", response_model=RequestFileOut)
def pin_number(
    request_id: int,
    body: PinIn,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequestFileOut:
    """«تثبيت» a national ID or family number from a source; the file after the re-check (R4)."""
    request = review_service.pin(db, ctx.user, request_id, body)
    return review_service.to_file(db, request, ctx.user)


@router.post("/requests/{request_id}/delete", response_model=RequestFileOut)
def delete_request(
    request_id: int,
    body: DeleteIn,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequestFileOut:
    """«حذف مشترك»: needs `review` and `delete`; a pending or rejected request only. The answer
    is the file in its deleted form (specs/011 contracts/api.md)."""
    request = deletion_service.delete(db, ctx.user, request_id, body)
    return review_service.to_file(db, request, ctx.user)


@router.get("/legacy-images/{image_id}", response_class=FileResponse)
def get_legacy_image(
    image_id: uuid.UUID,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """A legacy subscriber's card image for review admins (specs/014 R13). Never cached; every
    open is logged."""
    path = review_service.open_legacy_image(db, ctx.user, image_id)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/request-images/{image_id}", response_class=FileResponse)
def get_request_image(
    image_id: uuid.UUID,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Never cached; every open is logged (research R9)."""
    path = review_service.open_request_image(db, ctx.user, image_id)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )
