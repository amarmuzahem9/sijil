"""/api/drafts/* and /api/draft-images/* (specs/005 contracts/api.md).

Draft routes are marketer-only (`marketer_only`) and owner-checked in draft_service. The image
route (added with US2) also admits the main admin and `review` admins. Every draft call carries
`X-Client-Id`, one random UUID per page load of the form (research.md R3): it tells a save from
the same page apart from a save made on another device or another tab of the same session.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, current_user, require_roles
from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.schemas.drafts import CreateBody, DraftOut, PatchBody, VersionOut
from app.services import draft_service

router = APIRouter(tags=["drafts"])

marketer_only = require_roles("marketer")


def _parse_client_id(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def client_id(x_client_id: str | None = Header(default=None)) -> uuid.UUID:
    """Required on writes: a missing or malformed value → 422 `validation_error`."""
    parsed = _parse_client_id(x_client_id)
    if parsed is None:
        raise AppError("validation_error", 422)
    return parsed


def optional_client_id(x_client_id: str | None = Header(default=None)) -> uuid.UUID | None:
    """For reads (GET, version poll): used only to compute `same_client`."""
    return _parse_client_id(x_client_id)


# --- drafts (US1) ----------------------------------------------------------------------------


@router.put("/drafts/{draft_id}", response_model=DraftOut)
def put_draft(
    draft_id: uuid.UUID,
    body: CreateBody,
    response: Response,
    ctx: AuthContext = Depends(marketer_only),
    cid: uuid.UUID = Depends(client_id),
    db: Session = Depends(get_db),
) -> DraftOut:
    """Create-if-absent with the client's UUID (research.md R1): 201 created, 200 existing."""
    draft, created = draft_service.create_if_absent(db, ctx.user, cid, draft_id, body.changes)
    response.status_code = 201 if created else 200
    return draft_service.to_out(draft)


@router.get("/drafts/{draft_id}", response_model=DraftOut)
def get_draft(
    draft_id: uuid.UUID,
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> DraftOut:
    return draft_service.to_out(draft_service.get_owned(db, ctx.user, draft_id))


@router.get("/drafts/{draft_id}/version", response_model=VersionOut)
def get_draft_version(
    draft_id: uuid.UUID,
    ctx: AuthContext = Depends(marketer_only),
    cid: uuid.UUID | None = Depends(optional_client_id),
    db: Session = Depends(get_db),
) -> VersionOut:
    """Polled every 15 s by an open form (research.md R3)."""
    draft = draft_service.get_owned(db, ctx.user, draft_id)
    return VersionOut(
        version=draft.version,
        updated_at=draft.updated_at,
        same_client=cid is not None and draft.last_client_id == cid,
    )


@router.patch("/drafts/{draft_id}", response_model=DraftOut)
def patch_draft(
    draft_id: uuid.UUID,
    body: PatchBody,
    ctx: AuthContext = Depends(marketer_only),
    cid: uuid.UUID = Depends(client_id),
    db: Session = Depends(get_db),
) -> DraftOut:
    draft = draft_service.patch(db, ctx.user, cid, draft_id, body.version, body.changes)
    return draft_service.to_out(draft)


# --- card images (US2) -----------------------------------------------------------------------

# Multipart framing around the file; the file itself is capped by MAX_IMAGE_BYTES.
_MULTIPART_OVERHEAD = 64 * 1024


def _body_size_guard(request: Request) -> None:
    """Refuse an oversized body before it is parsed (multipart spools the whole file first)."""
    length = request.headers.get("content-length")
    if length is not None and length.isdigit():
        if int(length) > get_settings().max_image_bytes + _MULTIPART_OVERHEAD:
            raise AppError("image_too_large", 413)


@router.post(
    "/drafts/{draft_id}/images/{side}",
    response_model=DraftOut,
    dependencies=[Depends(_body_size_guard)],
)
def upload_image(
    draft_id: uuid.UUID,
    side: Literal["front", "back"],
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(marketer_only),
    cid: uuid.UUID = Depends(client_id),
    db: Session = Depends(get_db),
) -> DraftOut:
    draft = draft_service.save_image(db, ctx.user, cid, draft_id, side, file)
    return draft_service.to_out(draft)


@router.get("/draft-images/{image_id}", response_class=FileResponse)
def get_image(
    image_id: uuid.UUID,
    ctx: AuthContext = Depends(current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Owner, main admin or `review` admin only; never cached; every open is logged (R7)."""
    _, path = draft_service.open_image(db, ctx.user, image_id)
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )
