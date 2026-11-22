"""Audit viewer shapes (specs/002 contracts/api.md › Audit log)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ActorOut(BaseModel):
    id: int
    name: str
    role: str


class AuditEntryOut(BaseModel):
    id: int
    created_at: datetime
    action: str
    actor: ActorOut | None
    entity_type: str
    entity_id: str
    target: ActorOut | None
    # Settings items (feature 004): current area/plan name or tower code; null otherwise.
    target_label: str | None = None
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    has_more: bool
    next_before_id: int | None


class ActorList(BaseModel):
    items: list[ActorOut]
