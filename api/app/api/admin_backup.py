"""/api/admin/backup* — main admin only (specs/016 FR-016, contracts/api.md, system.md §10.10).

The app never reads the backup files: it shows the mirror tables the `backup` service keeps, and
a manual backup is a `requested` row the service picks up. Restore is not offered here; it is a
server operation (FR-012).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_roles
from app.core.timeutil import utc_now
from app.db import get_db
from app.errors import AppError
from app.models import BackupEvent, BackupRun, BackupStatus
from app.schemas.backup import (
    BackupPageOut,
    BackupStatusOut,
    DeployOut,
    DrillOut,
    EventOut,
    RunningOut,
    RunOut,
    RunRequestedOut,
    details,
)
from app.services import audit_service, backup_warnings

router = APIRouter(prefix="/admin/backup", tags=["backup"])
_main_admin = require_roles("super_admin")
ACTIVE = ("requested", "running")
RUNS_SHOWN = 40
DEPLOYS_SHOWN = 10


def _status(db: Session) -> BackupStatusOut:
    row = db.get(BackupStatus, 1)
    return BackupStatusOut(
        service_ok=backup_warnings.service_ok(row, utc_now()),
        heartbeat_at=row.heartbeat_at if row else None,
        nightly_at=row.nightly_at if row else None,
        free_bytes=row.free_bytes if row else None,
        total_bytes=row.total_bytes if row else None,
        min_free_bytes=row.min_free_bytes if row else None,
        backup_dir_bytes=row.backup_dir_bytes if row else None,
        external_dir=row.external_dir if row else "",
        key_configured=bool(row and row.key_configured),
    )


def _last(db: Session, type_: str) -> BackupEvent | None:
    return db.scalar(
        select(BackupEvent).where(BackupEvent.type == type_).order_by(BackupEvent.at.desc())
    )


@router.get("", response_model=BackupPageOut)
def page(_: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)) -> BackupPageOut:
    running = db.scalar(select(BackupRun).where(BackupRun.status.in_(ACTIVE)))
    runs = db.scalars(
        select(BackupRun)
        .where(BackupRun.status.in_(("succeeded", "failed")))
        .order_by(BackupRun.started_at.desc().nulls_last(), BackupRun.created_at.desc())
        .limit(RUNS_SHOWN)
    )
    external = _last(db, "external_copy")
    drill = _last(db, "drill")
    deploys = db.scalars(
        select(BackupEvent)
        .where(BackupEvent.type == "deploy")
        .order_by(BackupEvent.at.desc())
        .limit(DEPLOYS_SHOWN)
    )
    return BackupPageOut(
        status=_status(db),
        running=RunningOut.model_validate(running, from_attributes=True) if running else None,
        runs=[RunOut.model_validate(r, from_attributes=True) for r in runs],
        last_external=EventOut.model_validate(external, from_attributes=True) if external else None,
        last_drill=DrillOut(
            at=drill.at,
            result=drill.result,
            snapshot_id=drill.snapshot_id,
            source=details(drill.details, "source"),
            reason=details(drill.details, "reason"),
        )
        if drill
        else None,
        deploys=[
            DeployOut(
                at=d.at,
                result=d.result,
                mode=details(d.details, "mode"),
                commit=details(d.details, "new_commit"),
            )
            for d in deploys
        ],
        warnings=backup_warnings.compute(db, utc_now()),
    )


@router.post("/run", response_model=RunRequestedOut, status_code=202)
def request_run(
    ctx: AuthContext = Depends(_main_admin), db: Session = Depends(get_db)
) -> RunRequestedOut:
    if not backup_warnings.service_ok(db.get(BackupStatus, 1), utc_now()):
        raise AppError("backup_service_down", 503)
    if db.scalar(select(BackupRun.id).where(BackupRun.status.in_(ACTIVE))) is not None:
        raise AppError("backup_busy", 409)
    run_id = f"req-{uuid.uuid4().hex[:12]}"
    try:
        with db.begin_nested():
            db.add(
                BackupRun(id=run_id, kind="manual", status="requested", requested_by=ctx.user.id)
            )
    except IntegrityError:  # another request won the race (one active run at a time)
        raise AppError("backup_busy", 409) from None
    audit_service.record(
        db,
        actor_id=ctx.user.id,
        action="backup.manual_requested",
        entity_type="backup_run",
        entity_id=run_id,
        after={},
    )
    db.commit()
    return RunRequestedOut(id=run_id)
