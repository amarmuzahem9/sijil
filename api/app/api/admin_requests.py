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
from app.schemas.admin_requests import PendingList, RequestFileOut
from app.services import review_service

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


@router.get("/requests/{request_id}", response_model=RequestFileOut)
def get_request_file(
    request_id: int,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequestFileOut:
    """404 for a caller without `review`, the same as for a missing request."""
    return review_service.to_file(db, review_service.get_for_review(db, ctx.user, request_id))


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
