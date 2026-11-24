"""/api/admin/imports/legacy/* — import of the legacy Google Form subscribers (specs/014
contracts/api.md). Main admin or `reports` only (Principle IX); a preview belongs to its uploader,
and anyone else gets 404."""

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.db import get_db
from app.errors import AppError
from app.schemas.legacy_import import Preview
from app.services import legacy_file, legacy_import_service

router = APIRouter(prefix="/admin/imports/legacy", tags=["admin-imports"])

_reports = require_permission("reports")


def _read_capped(upload: UploadFile) -> bytes:
    data = upload.file.read(legacy_file.MAX_FILE_BYTES + 1)
    if len(data) > legacy_file.MAX_FILE_BYTES:
        raise AppError("import_file_too_large", 413)
    return data


@router.post("/previews", response_model=Preview, status_code=201)
def create_preview(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    preview = legacy_import_service.create_preview(db, ctx.user, file.filename, _read_capped(file))
    return legacy_import_service.summary(preview)


@router.get("/previews/{preview_id}", response_model=Preview)
def get_preview(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    return legacy_import_service.summary(
        legacy_import_service.get_preview(db, ctx.user, preview_id)
    )


@router.delete("/previews/{preview_id}", status_code=204)
def cancel_preview(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> Response:
    legacy_import_service.cancel(db, ctx.user, preview_id)
    return Response(status_code=204)
