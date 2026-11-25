"""/api/admin/imports/* — import of the legacy Google Form subscribers (`legacy/*`, specs/014
contracts/api.md) and of the SAS subscribers (`sas/*`, specs/015 contracts/api.md). Main admin or
`reports` only (Principle IX); a preview belongs to its uploader, and anyone else gets 404. URLs
carry preview ids only, and request bodies are never logged."""

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.db import get_db
from app.schemas.legacy_import import ChoicesIn, ImportSummary, Preview
from app.schemas.sas_import import SasPreview
from app.services import legacy_file, legacy_import_service, sas_import_service

router = APIRouter(prefix="/admin/imports", tags=["admin-imports"])
legacy = APIRouter(prefix="/legacy")
sas = APIRouter(prefix="/sas")

_reports = require_permission("reports")


def _read_capped(upload: UploadFile, limit: int = legacy_file.MAX_FILE_BYTES) -> bytes:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise legacy_file.too_large(limit)
    return data


@legacy.post("/previews", response_model=Preview, status_code=201)
def create_preview(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    preview = legacy_import_service.create_preview(db, ctx.user, file.filename, _read_capped(file))
    return legacy_import_service.summary(preview)


@legacy.get("/previews/{preview_id}", response_model=Preview)
def get_preview(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    return legacy_import_service.summary(
        legacy_import_service.get_preview(db, ctx.user, preview_id)
    )


@legacy.put("/previews/{preview_id}/choices", response_model=Preview)
def set_choices(
    preview_id: uuid.UUID,
    body: ChoicesIn,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    preview = legacy_import_service.set_choices(
        db, ctx.user, preview_id, [item.model_dump() for item in body.choices]
    )
    return legacy_import_service.summary(preview)


@legacy.post("/previews/{preview_id}/confirm", response_model=ImportSummary, status_code=201)
def confirm(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    return legacy_import_service.confirm(db, ctx.user, preview_id)


@legacy.delete("/previews/{preview_id}", status_code=204)
def cancel_preview(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> Response:
    legacy_import_service.cancel(db, ctx.user, preview_id)
    return Response(status_code=204)


# --- SAS (specs/015) ------------------------------------------------------------------------------


@sas.post("/previews", response_model=SasPreview, status_code=201)
def create_sas_preview(
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    data = _read_capped(file, legacy_file.SAS_MAX_FILE_BYTES)
    return sas_import_service.summary(
        sas_import_service.create_preview(db, ctx.user, file.filename, data)
    )


@sas.get("/previews/{preview_id}", response_model=SasPreview)
def get_sas_preview(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> dict:
    return sas_import_service.summary(sas_import_service.get_preview(db, ctx.user, preview_id))


@sas.delete("/previews/{preview_id}", status_code=204)
def cancel_sas_preview(
    preview_id: uuid.UUID,
    ctx: AuthContext = Depends(_reports),
    db: Session = Depends(get_db),
) -> Response:
    sas_import_service.cancel(db, ctx.user, preview_id)
    return Response(status_code=204)


router.include_router(legacy)
router.include_router(sas)
