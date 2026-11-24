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
    # specs/011 R12: the entry is about a request that was deleted later. The entry itself is
    # never changed; the page shows «سجل محذوف» for links such as a pin.
    entity_deleted: bool = False


class AuditPage(BaseModel):
    items: list[AuditEntryOut]
    has_more: bool
    next_before_id: int | None


class ActorList(BaseModel):
    items: list[ActorOut]
