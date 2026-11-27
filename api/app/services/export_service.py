"""The requests export (docs/system.md v1.25 §11, §13; specs/019 research R5–R8, R10).

Lifecycle: `create` → `preparing` → the job writes `requests.xlsx` and `manifest.json` into
EXPORTS_DIR/<id>/ → `ready` for 24 hours → `removed`. A failed build is `failed`, then `removed`.

Guards:
- identity data and images only for the main admin or `reports` + `review`, and only when the
  box was ticked; checked when asked for, when built and at every ticket and download (R1);
- one `preparing` export per admin; at most `MAX_ROWS` rows;
- the download takes a one-use ticket that lives `TICKET_TTL`, opened by its requester only (R7);
- the ZIP is streamed at download: the images are read from private storage then, so an image
  erased since the build is not sent, and no multi-GB copy is kept (R6);
- `requests.exported` is written when the file is ready, `export.downloaded` and one
  `image_access_log` row per image sent before streaming starts (R8, analysis C1, M1).

No row value reaches a log line (Principle II): only ids, counts and error class names.
"""

import hashlib
import hmac
import io
import json
import logging
import secrets
import shutil
import uuid
import zipfile
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, noload

from app.config import get_settings
from app.core import deletion_reasons, rejection_reasons
from app.core.access import has_any_permission
from app.core.report_period import PeriodError
from app.core.timeutil import BAGHDAD, utc_now
from app.db import get_sessionmaker
from app.errors import AppError
from app.models import Export, ImageAccessLog, Request, User
from app.schemas.reports import ReportFilters
from app.services import audit_service, export_sheet, image_store, report_service
from app.services.export_sheet import ExportRow

log = logging.getLogger("sijil.exports")

MAX_ROWS = 5000
KEEP_FOR = timedelta(hours=24)
TICKET_TTL = timedelta(seconds=60)
LIST_FOR = timedelta(days=7)
SWEEP_EVERY = timedelta(minutes=15)
SHEET = "requests.xlsx"
MANIFEST = "manifest.json"
_CHUNK = 1 << 16

can_export_identity = report_service.can_export_identity

_jobs = ThreadPoolExecutor(max_workers=2, thread_name_prefix="export")


def _submit_to_pool(export_id: uuid.UUID) -> None:
    _jobs.submit(_run_safely, export_id)


# Replaced in tests by a function that runs `run(export_id, session=<test session>)` at once.
submit: Callable[[uuid.UUID], None] = _submit_to_pool


def _run_safely(export_id: uuid.UUID) -> None:
    try:
        run(export_id)
    except Exception as exc:  # a worker must never die silently; no row data in the message
        log.error("export job crashed export=%s error=%s", export_id, type(exc).__name__)


# --- files ---------------------------------------------------------------------------------------


def exports_dir() -> Path:
    return Path(get_settings().exports_dir)


def folder(export_id: uuid.UUID | str) -> Path:
    return exports_dir() / str(uuid.UUID(str(export_id)))


def _remove_folder(export_id: uuid.UUID | str) -> None:
    shutil.rmtree(folder(export_id), ignore_errors=True)


# --- permissions ---------------------------------------------------------------------------------


def _may_export(user: User | None) -> bool:
    return (
        user is not None
        and user.is_active
        and user.archived_at is None
        and has_any_permission(user.role, user.permissions, ["reports"])
    )


def _may_hold(user: User | None, export: Export) -> bool:
    """The requester may still have this export: `reports`, and `review` for identity data."""
    return _may_export(user) and (not export.include_identity or can_export_identity(user))


def _remove(db: Session, export: Export) -> None:
    export.state = "removed"
    export.removed_at = utc_now()
    export.ticket_hash = None
    export.ticket_expires_at = None
    db.commit()
    _remove_folder(export.id)


# --- create --------------------------------------------------------------------------------------


def stored_filters(filters: ReportFilters) -> dict:
    """Ids, codes and days only (research R8)."""
    return filters.model_dump(mode="json", by_alias=True, exclude_none=True)


def create(db: Session, user: User, filters: ReportFilters, include_identity: bool) -> Export:
    if include_identity and not can_export_identity(user):
        raise AppError("identity_export_forbidden", 403)
    try:
        where = report_service.conditions(filters)
    except PeriodError:
        raise AppError("period_invalid", 422) from None
    rows = report_service.count(db, where)
    if rows == 0:
        raise AppError("no_rows", 422)
    if rows > MAX_ROWS:
        raise AppError("export_too_large", 422)
    busy = db.scalar(
        select(Export.id).where(Export.requester_id == user.id, Export.state == "preparing")
    )
    if busy is not None:
        raise AppError("export_in_progress", 409)
    export = Export(
        id=uuid.uuid4(),
        requester_id=user.id,
        filters=stored_filters(filters),
        include_identity=include_identity,
        state="preparing",
        created_at=utc_now(),
    )
    db.add(export)
    try:
        db.commit()
    except IntegrityError:  # two clicks at once: `exports_one_preparing`
        db.rollback()
        raise AppError("export_in_progress", 409) from None
    log.info("export created export=%s rows=%d identity=%s", export.id, rows, include_identity)
    submit(export.id)
    db.refresh(export)
    return export


# --- the job -------------------------------------------------------------------------------------


def _rejection(request: Request) -> str | None:
    if request.rejection_reason is None:
        return None
    if request.rejection_reason == "other" and request.rejection_note:
        return request.rejection_note
    return rejection_reasons.LABELS.get(request.rejection_reason, request.rejection_reason)


def _export_row(r: Request) -> ExportRow:
    return ExportRow(
        number=r.number,
        full_name=r.full_name,
        phone=r.phone,
        username=r.username,
        area=r.area_name,
        tower=report_service.tower_label(r.tower_name, r.tower_code),
        plan=r.plan_name,
        trial_price=r.trial_price,
        second_price=r.second_price,
        marketer=r.marketer.name,
        type=r.type,
        status=r.status,
        submitted_at=r.submitted_at,
        approved_at=r.approved_at,
        linked_at=r.linked_at,
        address=r.address,
        landmark=r.landmark,
        lat=r.location_lat,
        lng=r.location_lng,
        rejection_reason=_rejection(r),
        deleted=r.deleted_at is not None,
        deletion_reason=deletion_reasons.LABELS.get(r.deletion_reason or "", None),
        national_id=r.national_id,
        family_number=r.family_number,
        birth_date=r.birth_date,
        issue_date=r.issue_date,
        expiry_date=r.expiry_date,
        birth_place=r.birth_place,
        issuing_authority=r.issuing_authority,
    )


def _requests(db: Session, export: Export) -> list[Request]:
    filters = ReportFilters.model_validate(export.filters)
    # The period as the requester saw it: the Baghdad day the export was asked for.
    today = export.created_at.astimezone(BAGHDAD).date()
    where = report_service.conditions(filters, today=today)
    column = report_service.date_column(filters)
    return list(
        db.scalars(
            select(Request)
            .options(noload(Request.reasons), noload(Request.pins))
            .where(*where)
            .order_by(column.desc(), Request.id.desc())
            .limit(MAX_ROWS)
        )
    )


def _images(requests: list[Request]) -> tuple[list[dict], dict[int, set[str]], int]:
    """The manifest, the sides present per number, and the number of missing images."""
    manifest: list[dict] = []
    present: dict[int, set[str]] = {}
    missing = 0
    for r in requests:
        if r.deleted_at is not None:
            continue
        sides: set[str] = set()
        for image in r.images:
            if image_store.open_path(image.file_name).is_file():
                sides.add(image.side)
                manifest.append(
                    {
                        "number": r.number,
                        "request_id": r.id,
                        "side": image.side,
                        "image_id": str(image.id),
                        "file_name": image.file_name,
                    }
                )
        present[r.number] = sides
        missing += 2 - len(sides)
    return manifest, present, missing


def _fail(db: Session, export_id: uuid.UUID, code: str) -> None:
    db.rollback()
    db.execute(
        update(Export)
        .where(Export.id == export_id, Export.state == "preparing")
        .values(state="failed", error_code=code)
    )
    db.commit()
    _remove_folder(export_id)


def run(export_id: uuid.UUID, session: Session | None = None) -> None:
    db = session or get_sessionmaker()()
    try:
        export = db.get(Export, export_id)
        if export is None or export.state != "preparing":
            return
        user = db.get(User, export.requester_id)
        if not _may_hold(user, export):
            _fail(db, export_id, "permission_lost")
            log.info("export refused at build export=%s", export_id)
            return
        requests = _requests(db, export)
        rows = [_export_row(r) for r in requests]
        manifest, present, missing = _images(requests) if export.include_identity else ([], {}, 0)
        data = export_sheet.request_workbook(rows, identity=export.include_identity, images=present)
        target = folder(export_id)
        target.mkdir(parents=True, exist_ok=True)
        (target / SHEET).write_bytes(data)
        (target / MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
        now = utc_now()
        export.state = "ready"
        export.ready_at = now
        export.expires_at = now + KEEP_FOR
        export.row_count = len(rows)
        export.missing_images = missing
        audit_service.record(
            db,
            actor_id=export.requester_id,
            action="requests.exported",
            entity_type="export",
            entity_id=str(export.id),
            after={
                "filters": export.filters,
                "row_count": len(rows),
                "numbers": [r.number for r in requests],
                "identity": export.include_identity,
                "missing_images": missing,
            },
        )
        db.commit()
        log.info("export ready export=%s rows=%d missing=%d", export_id, len(rows), missing)
    except Exception as exc:
        log.error("export build failed export=%s error=%s", export_id, type(exc).__name__)
        _fail(db, export_id, "build_failed")
    finally:
        if session is None:
            db.close()


# --- reading -------------------------------------------------------------------------------------


def own(db: Session, user: User, export_id: uuid.UUID) -> Export:
    export = db.get(Export, export_id)
    if export is None or export.requester_id != user.id:
        raise AppError("not_found", 404)
    return export


def list_own(db: Session, user: User) -> list[Export]:
    since = utc_now() - LIST_FOR
    return list(
        db.scalars(
            select(Export)
            .where(Export.requester_id == user.id, Export.created_at >= since)
            .order_by(Export.created_at.desc())
        )
    )


# --- ticket and download (research R7) -----------------------------------------------------------


def _hash(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()


def _usable(db: Session, export: Export) -> None:
    """Raises unless the export is ready, unexpired and its folder is there."""
    if export.state in ("preparing", "failed"):
        raise AppError("export_not_ready", 409)
    if export.state == "removed":
        raise AppError("export_removed", 410)
    assert export.expires_at is not None
    if export.expires_at <= utc_now() or not (folder(export.id) / SHEET).is_file():
        _remove(db, export)
        raise AppError("export_removed", 410)


def issue_ticket(db: Session, user: User, export_id: uuid.UUID) -> str:
    export = own(db, user, export_id)
    _usable(db, export)
    if not _may_hold(user, export):
        _remove(db, export)
        log.info("export removed, permission lost export=%s", export.id)
        raise AppError("identity_export_forbidden", 403)
    ticket = secrets.token_urlsafe(32)
    export.ticket_hash = _hash(ticket)
    export.ticket_expires_at = utc_now() + TICKET_TTL
    db.commit()
    return f"/api/admin/exports/{export.id}/download?ticket={ticket}"


@dataclass(frozen=True)
class Download:
    sheet: Path
    images: list[tuple[str, Path]]
    file_name: str


def open_download(db: Session, export_id: uuid.UUID, ticket: str) -> Download:
    export = db.get(Export, export_id)
    now = utc_now()
    if (
        export is None
        or export.ticket_hash is None
        or export.ticket_expires_at is None
        or export.ticket_expires_at < now
        or not hmac.compare_digest(_hash(ticket), export.ticket_hash)
    ):
        raise AppError("ticket_invalid", 403)
    # Single use: the ticket is spent before anything else is checked.
    export.ticket_hash = None
    export.ticket_expires_at = None
    db.commit()
    user = db.get(User, export.requester_id)
    if not _may_export(user):
        raise AppError("forbidden", 403)
    assert user is not None
    if not _may_hold(user, export):
        _remove(db, export)
        log.info("export removed at download, permission lost export=%s", export.id)
        raise AppError("identity_export_forbidden", 403)
    _usable(db, export)
    target = folder(export.id)
    images: list[tuple[str, Path]] = []
    if export.include_identity:
        manifest = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
        for item in manifest:
            path = image_store.open_path(item["file_name"])
            if not path.is_file():
                continue  # erased since the build (§7.4): never sent
            images.append((f"cards/{export_sheet.image_name(item['number'], item['side'])}", path))
            db.add(
                ImageAccessLog(
                    user_id=user.id,
                    image_id=uuid.UUID(item["image_id"]),
                    request_id=item["request_id"],
                    side=item["side"],
                    purpose="export",
                )
            )
    audit_service.record(
        db,
        actor_id=user.id,
        action="export.downloaded",
        entity_type="export",
        entity_id=str(export.id),
        after={"images": len(images)},
    )
    db.commit()
    stamp = (export.ready_at or now).astimezone(BAGHDAD).strftime("%Y-%m-%d-%H%M")
    log.info("export downloaded export=%s images=%d", export.id, len(images))
    return Download(sheet=target / SHEET, images=images, file_name=f"sijil-requests-{stamp}.zip")


class _Sink(io.RawIOBase):
    """An unseekable stream that hands out what the ZIP writer wrote (research R6)."""

    def __init__(self) -> None:
        self._parts: list[bytes] = []

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self._parts.append(bytes(b))
        return len(b)

    def take(self) -> bytes:
        data = b"".join(self._parts)
        self._parts.clear()
        return data


def _copy(zf: zipfile.ZipFile, sink: _Sink, name: str, path: Path) -> Iterator[bytes]:
    with path.open("rb") as src, zf.open(name, "w", force_zip64=True) as dst:
        while chunk := src.read(_CHUNK):
            dst.write(chunk)
            yield sink.take()


def stream_zip(download: Download) -> Iterator[bytes]:
    """`requests.xlsx` then `cards/…`, stored (JPEGs and xlsx do not shrink), ZIP64."""
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        yield from _copy(zf, sink, SHEET, download.sheet)
        for name, path in download.images:
            try:
                yield from _copy(zf, sink, name, path)
            except FileNotFoundError:
                continue  # erased in the last moment: skipped
    yield sink.take()


# --- sweeping (research R10) ---------------------------------------------------------------------


def sweep_at_startup(session: Session | None = None) -> None:
    """Builds left `preparing` by a previous process become `failed`."""
    db = session or get_sessionmaker()()
    try:
        left = list(db.scalars(select(Export.id).where(Export.state == "preparing")))
        if left:
            db.execute(
                update(Export)
                .where(Export.id.in_(left))
                .values(state="failed", error_code="interrupted")
            )
            db.commit()
            for export_id in left:
                _remove_folder(export_id)
            log.info("exports interrupted at startup count=%d", len(left))
    finally:
        if session is None:
            db.close()


def sweep_expired(session: Session | None = None) -> int:
    """Remove ready exports past their time and failed ones, and any folder without a live row.
    Returns the number of rows moved to `removed`."""
    db = session or get_sessionmaker()()
    try:
        now = utc_now()
        gone = list(
            db.scalars(
                select(Export).where(
                    # A failed row stays «فشل التجهيز» for its owner as long as a file would
                    # have; its folder is already gone (`_fail`, and the stray check below).
                    ((Export.state == "failed") & (Export.created_at <= now - KEEP_FOR))
                    | ((Export.state == "ready") & (Export.expires_at <= now))
                )
            )
        )
        for export in gone:
            export.state = "removed"
            export.removed_at = now
            export.ticket_hash = None
            export.ticket_expires_at = None
        if gone:
            db.commit()
        for export in gone:
            _remove_folder(export.id)
        root = exports_dir()
        if root.is_dir():
            live = {
                str(i)
                for i in db.scalars(
                    select(Export.id).where(Export.state.in_(("preparing", "ready")))
                )
            }
            for child in root.iterdir():
                if child.name not in live:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
        if gone:
            log.info("exports removed count=%d", len(gone))
        return len(gone)
    finally:
        if session is None:
            db.close()
