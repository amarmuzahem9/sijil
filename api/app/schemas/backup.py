"""The backup page (specs/016 contracts/api.md). Ids, times, sizes, counts and codes only."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class BackupStatusOut(BaseModel):
    service_ok: bool
    heartbeat_at: datetime | None
    nightly_at: str | None
    free_bytes: int | None
    total_bytes: int | None
    min_free_bytes: int | None
    backup_dir_bytes: int | None
    external_dir: str
    key_configured: bool


class RunningOut(BaseModel):
    id: str
    kind: str
    status: str
    started_at: datetime | None


class RunOut(BaseModel):
    id: str
    snapshot_id: str | None
    kind: str
    status: str
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None
    total_size: int | None
    image_count: int | None
    counts: dict[str, int] | None


class EventOut(BaseModel):
    at: datetime
    result: str
    snapshot_id: str | None


class DrillOut(EventOut):
    source: str | None
    reason: str | None


class DeployOut(BaseModel):
    at: datetime
    result: str
    mode: str | None
    commit: str | None


class BackupPageOut(BaseModel):
    status: BackupStatusOut
    running: RunningOut | None
    runs: list[RunOut]
    last_external: EventOut | None
    last_drill: DrillOut | None
    deploys: list[DeployOut]
    warnings: list[str]


class RunRequestedOut(BaseModel):
    id: str


def details(value: dict[str, Any] | None, key: str) -> Any:
    return (value or {}).get(key)
