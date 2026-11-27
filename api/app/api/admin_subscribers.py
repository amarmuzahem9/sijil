"""/api/admin/subscribers — «المشتركون» (docs/system.md v1.24 §10 item 4; specs/018 contracts).

The main admin and admins with `review`, `link` or `reports`; anyone else gets 403 (Principle IX).
A search by national ID or family number needs `review`: it is refused before any lookup, so the
answer is the same whether the number exists or not (owner Q2). Read-only (owner Q3).
"""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_permission
from app.core.subscriber_search import classify
from app.db import get_db
from app.errors import AppError
from app.schemas.subscribers import ResultRow, SearchOut
from app.services import subscriber_file as subscriber_file_service
from app.services import subscriber_search
from app.services.review_service import can_review

router = APIRouter(prefix="/admin/subscribers", tags=["admin-subscribers"])

readers = require_permission("review", "link", "reports")
log = logging.getLogger("sijil.subscribers")


@router.get("", response_model=SearchOut)
def search(
    q: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    limit: int = Query(default=50, ge=1, le=50),
    ctx: AuthContext = Depends(readers),
    db: Session = Depends(get_db),
) -> SearchOut:
    term = classify(q)
    if term is None:
        raise AppError("search_unclear", 422)
    if term.requires_review and not can_review(ctx.user):
        raise AppError("identity_search_forbidden", 403)
    rows, total = subscriber_search.search(db, term, offset, limit)
    # The kind and the count only: never the query text (FR-012).
    log.info("subscriber search kind=%s results=%s", term.kind, total)
    return SearchOut(kind=term.kind, items=[ResultRow(**asdict(r)) for r in rows], total=total)


@router.get("/{source}/{ref}")
def subscriber_file(
    source: str,
    ref: str,
    ctx: AuthContext = Depends(readers),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """The file of one record and its linked records (FR-007, FR-008). Built as an allow-list per
    caller: identity keys are absent, not null, without `review` (FR-009). 404 when unknown."""
    body = subscriber_file_service.build(db, ctx.user, source, ref)
    # The record reference only (FR-012).
    log.info("subscriber file %s:%s", source, ref)
    return JSONResponse(jsonable_encoder(body))
