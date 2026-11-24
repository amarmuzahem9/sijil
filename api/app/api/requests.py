"""/api/requests: the marketer's own submitted requests (specs/008 contracts/api.md, FR-019).

Only the owner sees a request; anyone else gets 404 (Principle IX). Admin request pages are 010.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.db import get_db
from app.schemas.requests import RequestList, RequestOut, RequestStatus
from app.services import submit_service

router = APIRouter(tags=["requests"])

marketer_only = require_roles("marketer")


@router.get("/requests", response_model=RequestList)
def list_requests(
    status: list[RequestStatus] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> RequestList:
    """Newest first; `status` may repeat. `q` searches by number, phone or name (specs/012 R8)."""
    return RequestList(items=submit_service.list_own(db, ctx.user, status, q))


@router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(
    request_id: int,
    ctx: AuthContext = Depends(marketer_only),
    db: Session = Depends(get_db),
) -> RequestOut:
    return submit_service.to_out(submit_service.get_own(db, ctx.user, request_id))
