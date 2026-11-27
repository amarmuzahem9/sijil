"""/api/admin/reports and /api/admin/exports — «التقارير والتصدير» (docs/system.md v1.25 §10 item 8,
§11, §13; specs/019 contracts/api.md).

The main admin and admins with `reports`; anyone else, marketers included, gets 403 (FR-001,
Principle IX). The report has no identity, contact or money field (FR-002, FR-016). The download
takes a one-use ticket instead of the session (research R7); everything else needs the session.
"""

import logging
import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.core.report_period import PeriodError
from app.db import get_db
from app.errors import AppError
from app.models import Export
from app.schemas.reports import (
    ExportCreate,
    ExportList,
    ExportOut,
    ReportFilters,
    ReportOptions,
    ReportOut,
    ReportRow,
    ReportSummary,
    TicketOut,
)
from app.services import export_service, report_service

router = APIRouter(tags=["admin-reports"])

readers = require_permission("reports")
log = logging.getLogger("sijil.reports")


def _where(filters: ReportFilters):
    try:
        return report_service.conditions(filters)
    except PeriodError:
        raise AppError("period_invalid", 422) from None


@router.get("/admin/reports/options", response_model=ReportOptions)
def report_options(
    _: AuthContext = Depends(readers), db: Session = Depends(get_db)
) -> ReportOptions:
    return ReportOptions(**report_service.options(db))


@router.get("/admin/reports/requests", response_model=ReportOut)
def requests_report(
    filters: Annotated[ReportFilters, Query()],
    page: int = Query(default=1, ge=1, le=10_000),
    ctx: AuthContext = Depends(readers),
    db: Session = Depends(get_db),
) -> ReportOut:
    where = _where(filters)
    total = report_service.count(db, where)
    rows = report_service.page(db, filters, where, page)
    summary = report_service.summaries(db, where)
    # Counts only: never a filter value tied to a person, never a row (Principle II).
    log.info("requests report total=%s page=%s", total, page)
    return ReportOut(
        total=total,
        page=page,
        page_size=report_service.PAGE_SIZE,
        rows=[ReportRow(**asdict(r)) for r in rows],
        summary=ReportSummary(**asdict(summary)),
        can_export_identity=report_service.can_export_identity(ctx.user),
    )


# --- exports (research R5–R8) --------------------------------------------------------------------


def _out(export: Export) -> ExportOut:
    return ExportOut(
        id=str(export.id),
        state=export.state,  # type: ignore[arg-type]
        include_identity=export.include_identity,
        row_count=export.row_count,
        missing_images=export.missing_images,
        filters=export.filters,
        created_at=export.created_at,
        ready_at=export.ready_at,
        expires_at=export.expires_at,
        error=export.error_code,
    )


def _export_id(export_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(export_id)
    except ValueError:
        raise AppError("not_found", 404) from None


@router.post("/admin/exports", response_model=ExportOut, status_code=202)
def create_export(
    body: ExportCreate,
    ctx: AuthContext = Depends(readers),
    db: Session = Depends(get_db),
) -> ExportOut:
    export_service.sweep_expired(session=db)
    filters = ReportFilters.model_validate(
        body.model_dump(by_alias=True, exclude={"include_identity"})
    )
    return _out(export_service.create(db, ctx.user, filters, body.include_identity))


@router.get("/admin/exports", response_model=ExportList)
def list_exports(ctx: AuthContext = Depends(readers), db: Session = Depends(get_db)) -> ExportList:
    export_service.sweep_expired(session=db)
    return ExportList(items=[_out(e) for e in export_service.list_own(db, ctx.user)])


@router.get("/admin/exports/{export_id}", response_model=ExportOut)
def get_export(
    export_id: str, ctx: AuthContext = Depends(readers), db: Session = Depends(get_db)
) -> ExportOut:
    export_service.sweep_expired(session=db)
    return _out(export_service.own(db, ctx.user, _export_id(export_id)))


@router.post("/admin/exports/{export_id}/ticket", response_model=TicketOut)
def export_ticket(
    export_id: str, ctx: AuthContext = Depends(readers), db: Session = Depends(get_db)
) -> TicketOut:
    url = export_service.issue_ticket(db, ctx.user, _export_id(export_id))
    return TicketOut(url=url, expires_in=int(export_service.TICKET_TTL.total_seconds()))


@router.get("/admin/exports/{export_id}/download")
def download_export(
    export_id: str,
    ticket: str = Query(default="", max_length=200),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """No session: the one-use ticket alone opens it, for its requester's export only (R7)."""
    try:
        target = uuid.UUID(export_id)
    except ValueError:
        raise AppError("ticket_invalid", 403) from None
    download = export_service.open_download(db, target, ticket)
    return StreamingResponse(
        export_service.stream_zip(download),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{download.file_name}"',
            "Cache-Control": "no-store",
        },
    )
