"""/api/admin/requests/* and /api/admin/request-images/* — admin review (specs/010
contracts/api.md).

Every route needs the main admin or an admin with `review`, checked on the server (Principle IX).
The list answers 403 to anyone else; a single request or image answers 404, so its existence does
not leak. Routes are added per user story (tasks.md batches 2–4).
"""

from fastapi import APIRouter

from app.api.deps import require_permission

router = APIRouter(prefix="/admin", tags=["admin-review"])

review_only = require_permission("review")
