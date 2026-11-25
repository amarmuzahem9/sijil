"""Backup warnings for the main admin (specs/016 FR-017, research R12, contracts/api.md).

Computed from the mirror tables the `backup` service keeps (no access to the backup files).
Codes come in a fixed order; no subscriber data.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BackupEvent, BackupRun, BackupStatus

SERVICE_STALE = timedelta(minutes=10)
BACKUP_MAX_AGE = timedelta(hours=36)
WEEKLY_MAX_AGE = timedelta(days=8)
# Warn before backups are refused: free space under twice the margin.
DISK_WARNING_FACTOR = 2

CODES = (
    "service_down",
    "no_key",
    "last_failed",
    "no_recent_backup",
    "disk_low",
    "drill_failed_or_overdue",
    "external_overdue",
)
TEXTS = {
    "service_down": "خدمة النسخ متوقفة",
    "no_key": "لم يُضبط مفتاح النسخ",
    "last_failed": "فشل آخر نسخ احتياطي",
    "no_recent_backup": "لا توجد نسخة ناجحة منذ أكثر من 36 ساعة",
    "disk_low": "مساحة السيرفر قليلة",
    "drill_failed_or_overdue": "تجربة الاسترجاع فشلت أو متأخرة",
    "external_overdue": "النسخة الأسبوعية على الهارد الخارجي متأخرة",
}


def service_ok(status: BackupStatus | None, now: datetime) -> bool:
    return bool(status and status.heartbeat_at and now - status.heartbeat_at <= SERVICE_STALE)


def _last_event(db: Session, type_: str) -> BackupEvent | None:
    return db.scalar(
        select(BackupEvent).where(BackupEvent.type == type_).order_by(BackupEvent.at.desc())
    )


def _last_good_event(db: Session, type_: str, good: str) -> BackupEvent | None:
    return db.scalar(
        select(BackupEvent)
        .where(BackupEvent.type == type_, BackupEvent.result == good)
        .order_by(BackupEvent.at.desc())
    )


def compute(db: Session, now: datetime) -> list[str]:
    status = db.get(BackupStatus, 1)
    found: set[str] = set()
    if not service_ok(status, now):
        found.add("service_down")
    if status is not None and not status.key_configured:
        found.add("no_key")

    last = db.scalar(
        select(BackupRun)
        .where(BackupRun.status.in_(("succeeded", "failed")))
        .order_by(BackupRun.finished_at.desc().nulls_last(), BackupRun.created_at.desc())
    )
    if last is not None and last.status == "failed":
        found.add("last_failed")
    newest_ok = db.scalar(
        select(BackupRun.finished_at)
        .where(BackupRun.status == "succeeded")
        .order_by(BackupRun.finished_at.desc())
    )
    if newest_ok is None or now - newest_ok > BACKUP_MAX_AGE:
        found.add("no_recent_backup")

    if (
        status is not None
        and status.free_bytes is not None
        and status.min_free_bytes is not None
        and status.free_bytes < DISK_WARNING_FACTOR * status.min_free_bytes
    ):
        found.add("disk_low")

    drill = _last_event(db, "drill")
    if drill is None or drill.result != "passed" or now - drill.at > WEEKLY_MAX_AGE:
        found.add("drill_failed_or_overdue")
    external = _last_good_event(db, "external_copy", "succeeded")
    if external is None or now - external.at > WEEKLY_MAX_AGE:
        found.add("external_overdue")
    return [code for code in CODES if code in found]
