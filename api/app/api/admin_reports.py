"""/api/admin/reports — «التقارير والتصدير» (docs/system.md v1.25 §10 item 8, §11; specs/019
contracts/api.md).

The main admin and admins with `reports`; anyone else, marketers included, gets 403 (FR-001,
Principle IX). The report has no identity, contact or money field (FR-002, FR-016).
"""

import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.core.report_period import PeriodError
from app.db import get_db
from app.errors import AppError
from app.schemas.reports import ReportFilters, ReportOptions, ReportOut, ReportRow, ReportSummary
from app.services import report_service

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])

readers = require_permission("reports")
log = logging.getLogger("sijil.reports")


def _where(filters: ReportFilters):
    try:
        return report_service.conditions(filters)
    except PeriodError:
        raise AppError("period_invalid", 422) from None


@router.get("/options", response_model=ReportOptions)
def report_options(
    _: AuthContext = Depends(readers), db: Session = Depends(get_db)
) -> ReportOptions:
    return ReportOptions(**report_service.options(db))


@router.get("/requests", response_model=ReportOut)
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
