"""Import of the legacy Google Form subscribers — preview and image fetching (docs/system.md 1.19
§12.1; specs/014 research R6–R9; contracts/api.md).

Upload → `create_preview` reads the file in memory, cleans every row and stores an unsaved preview
(`legacy_import_previews`, one per admin, one hour). A background job (`run`) downloads every Drive
image into staged files of the private volume, then computes the flags and marks the preview
`ready`. No legacy subscriber exists until confirmation (batch 3). Staged files belong to the
preview: they are removed with it, and `draft_service.referenced_file_names` keeps them from
`prune-orphans` meanwhile.

Rows hold personal data: they are never logged. Log lines carry preview ids and counts only.
"""

import copy
import logging
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core import legacy_row
from app.core.timeutil import utc_now
from app.db import get_sessionmaker
from app.errors import AppError
from app.models import LegacyImportPreview, LegacySubscriber, Request, User
from app.models.request import ACTIVE_STATUSES
from app.services import image_store, legacy_file
from app.services.drive_fetcher import Fetcher, FetchResult, get_fetcher

log = logging.getLogger("sijil.legacy_import")

PREVIEW_TTL = timedelta(hours=1)
DOWNLOAD_WORKERS = 4
PROGRESS_EVERY = 10
SIDES = ("front", "back")

_jobs = ThreadPoolExecutor(max_workers=2, thread_name_prefix="legacy-import")
_downloads = ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS, thread_name_prefix="legacy-drive")


def _submit_to_pool(preview_id: uuid.UUID) -> None:
    _jobs.submit(_run_safely, preview_id)


# Replaced in tests by a function that runs `run(preview_id, session=<test session>)` at once.
submit: Callable[[uuid.UUID], None] = _submit_to_pool


def _run_safely(preview_id: uuid.UUID) -> None:
    try:
        run(preview_id)
    except Exception:  # a worker must never die silently; no row data in the message
        log.exception("legacy preview job failed preview=%s", preview_id)


# --- files of a preview --------------------------------------------------------------------------


def _staged(rows: list[dict[str, Any]]) -> list[str]:
    return [
        image["staged_file"]
        for row in rows
        for image in row.get("images", {}).values()
        if image.get("staged_file")
    ]


def _remove(db: Session, previews: list[LegacyImportPreview]) -> None:
    """Delete preview rows (committed), then their staged files."""
    if not previews:
        return
    files = [name for p in previews for name in _staged(p.rows)]
    db.execute(
        delete(LegacyImportPreview).where(LegacyImportPreview.id.in_([p.id for p in previews]))
    )
    db.commit()
    for name in files:
        image_store.unlink_quietly(name)


def staged_file_names(db: Session) -> set[str]:
    return {name for rows in db.scalars(select(LegacyImportPreview.rows)) for name in _staged(rows)}


def sweep_expired(db: Session) -> int:
    expired = list(
        db.scalars(select(LegacyImportPreview).where(LegacyImportPreview.expires_at <= utc_now()))
    )
    _remove(db, expired)
    return len(expired)


def sweep_stale(db: Session) -> int:
    """A preview still `fetching` when the process starts lost its job: it becomes `failed`."""
    result = db.execute(
        update(LegacyImportPreview)
        .where(LegacyImportPreview.status == "fetching")
        .values(status="failed")
    )
    db.commit()
    return result.rowcount or 0


def sweep_at_startup() -> None:
    db = get_sessionmaker()()
    try:
        stale = sweep_stale(db)
        expired = sweep_expired(db)
        if stale or expired:
            log.warning(
                "legacy previews: %d failed after restart, %d expired removed", stale, expired
            )
    except Exception:
        log.exception("sweeping legacy previews failed")
    finally:
        db.close()


# --- stored data the flags compare with ----------------------------------------------------------


def load_existing(db: Session, rows: list[dict[str, Any]]) -> legacy_row.Existing:
    numbers = {r["legacy_number"] for r in rows if r["legacy_number"]}
    phones = {r["phone"] for r in rows if r["phone"]}
    keys = {r["family_key"] for r in rows if r["family_key"]}
    stored_numbers = (
        set(
            db.scalars(
                select(LegacySubscriber.legacy_number).where(
                    LegacySubscriber.legacy_number.in_(numbers)
                )
            )
        )
        if numbers
        else set()
    )
    legacy_phones: set[str] = set()
    legacy_keys: set[str] = set()
    sijil_phones: dict[str, list[str]] = {}
    sijil_keys: dict[str, list[str]] = {}
    if phones or keys:
        for phone, key in db.execute(
            select(LegacySubscriber.phone, LegacySubscriber.family_key).where(
                LegacySubscriber.counts_in_check,
                or_(LegacySubscriber.phone.in_(phones), LegacySubscriber.family_key.in_(keys)),
            )
        ):
            if phone in phones:
                legacy_phones.add(phone)
            if key in keys:
                legacy_keys.add(key)
        for request in db.scalars(
            select(Request).where(
                or_(Request.phone.in_(phones), Request.family_key.in_(keys)),
                Request.status.in_(ACTIVE_STATUSES),
                Request.deleted_at.is_(None),
            )
        ):
            if request.phone in phones:
                sijil_phones.setdefault(request.phone, []).append(request.number_label)
            if request.family_key in keys:
                sijil_keys.setdefault(request.family_key, []).append(request.number_label)
    return legacy_row.Existing(
        legacy_numbers=frozenset(stored_numbers),
        legacy_phones=frozenset(legacy_phones),
        legacy_family_keys=frozenset(legacy_keys),
        sijil_phones=sijil_phones,
        sijil_family_keys=sijil_keys,
    )


# --- upload --------------------------------------------------------------------------------------


def _clean_file_name(name: str | None) -> str:
    return (Path(name or "").name or "file")[:200]


def create_preview(
    db: Session, user: User, file_name: str | None, data: bytes
) -> LegacyImportPreview:
    headers, body = legacy_file.read_table(data)
    try:
        columns = legacy_row.match_headers(headers)
    except legacy_row.MissingColumns as missing:
        raise AppError(
            "import_columns_missing",
            422,
            message="الملف ينقصه عمود: " + "، ".join(missing.columns),
            extra={"columns": missing.columns},
        ) from None

    rows: list[dict[str, Any]] = []
    for offset, cells in enumerate(body):
        raw = {key: cells[i] if i < len(cells) else None for key, i in columns.items()}
        row = legacy_row.clean_row(offset + 2, raw)  # file row number; the header is row 1
        row["base_flags"] = row.pop("flags")
        row["choice"] = None
        row["corrected_family_number"] = None
        rows.append(row)

    imported = load_existing(db, rows).legacy_numbers
    total = 0
    for row in rows:
        row["images"] = {}
        for side in SIDES:
            if row["legacy_number"] in imported:
                row["images"][side] = {"outcome": "skipped"}
            elif row["drive_ids"][side] is None:
                row["images"][side] = {"outcome": "missing"}
            else:
                row["images"][side] = {"outcome": "pending"}
                total += 1

    sweep_expired(db)
    _remove(
        db,
        list(
            db.scalars(select(LegacyImportPreview).where(LegacyImportPreview.created_by == user.id))
        ),
    )
    preview = LegacyImportPreview(
        id=uuid.uuid4(),
        created_by=user.id,
        expires_at=utc_now() + PREVIEW_TTL,
        status="fetching",
        file_name=_clean_file_name(file_name),
        images_total=total,
        images_done=0,
        rows=rows,
    )
    db.add(preview)
    db.commit()
    log.info("legacy preview created preview=%s rows=%d images=%d", preview.id, len(rows), total)
    submit(preview.id)
    db.refresh(preview)
    return preview


# --- the job -------------------------------------------------------------------------------------


def _fetch_one(fetcher: Fetcher, file_id: str) -> dict[str, Any]:
    """Download and store one image; returns the row's image entry. Runs on a download thread."""
    try:
        result: FetchResult = fetcher.fetch(file_id)
    except Exception:  # an adapter bug must not stop the preview
        log.warning("drive fetch raised")
        return {"outcome": "network"}
    if result.outcome != "ok" or result.data is None:
        return {"outcome": result.outcome}
    try:
        stored = image_store.save_bytes(result.data)
    except AppError:
        return {"outcome": "not_image"}
    return {
        "outcome": "ok",
        "staged_file": stored.file_name,
        "width": stored.width,
        "height": stored.height,
        "size_bytes": stored.size_bytes,
    }


def _save_progress(db: Session, preview_id: uuid.UUID, rows: list, done: int, **values) -> bool:
    """Write progress if the preview still exists and is still fetching (not cancelled)."""
    result = db.execute(
        update(LegacyImportPreview)
        .where(LegacyImportPreview.id == preview_id, LegacyImportPreview.status == "fetching")
        .values(rows=rows, images_done=done, **values)
    )
    db.commit()
    return bool(result.rowcount)


def run(
    preview_id: uuid.UUID, session: Session | None = None, fetcher: Fetcher | None = None
) -> None:
    db = session or get_sessionmaker()()
    fetcher = fetcher or get_fetcher()
    try:
        preview = db.get(LegacyImportPreview, preview_id)
        if preview is None or preview.status != "fetching":
            return
        rows = copy.deepcopy(preview.rows)
        by_index = {row["index"]: row for row in rows}
        jobs = {
            _downloads.submit(_fetch_one, fetcher, row["drive_ids"][side]): (row["index"], side)
            for row in rows
            for side in SIDES
            if row["images"][side]["outcome"] == "pending"
        }
        done = 0
        alive = True
        for future in as_completed(jobs):
            index, side = jobs[future]
            by_index[index]["images"][side] = future.result()
            done += 1
            if alive and done % PROGRESS_EVERY == 0:
                alive = _save_progress(db, preview_id, rows, done)
        if not alive or not _save_progress(
            db,
            preview_id,
            legacy_row.compute_flags(rows, load_existing(db, rows)),
            done,
            status="ready",
        ):
            # Cancelled or replaced while fetching: its files belong to nobody.
            for name in _staged(rows):
                image_store.unlink_quietly(name)
            log.info("legacy preview gone while fetching preview=%s", preview_id)
            return
        log.info("legacy preview ready preview=%s images=%d", preview_id, done)
    except Exception:
        db.rollback()
        db.execute(
            update(LegacyImportPreview)
            .where(LegacyImportPreview.id == preview_id)
            .values(status="failed")
        )
        db.commit()
        raise
    finally:
        if session is None:
            db.close()


# --- reading and cancelling ----------------------------------------------------------------------


def get_preview(db: Session, user: User, preview_id: uuid.UUID) -> LegacyImportPreview:
    sweep_expired(db)
    preview = db.get(LegacyImportPreview, preview_id)
    if preview is None or preview.created_by != user.id:
        raise AppError("preview_not_found", 404)
    db.refresh(preview)
    return preview


def cancel(db: Session, user: User, preview_id: uuid.UUID) -> None:
    _remove(db, [get_preview(db, user, preview_id)])


def summary(preview: LegacyImportPreview) -> dict[str, Any]:
    """The `Preview` body of contracts/api.md."""
    rows = preview.rows
    out: dict[str, Any] = {
        "id": preview.id,
        "status": preview.status,
        "file_name": preview.file_name,
        "expires_at": preview.expires_at,
        "images_total": preview.images_total,
        "images_done": preview.images_done,
    }
    values: dict[str | None, dict[str, Any]] = {}
    for row in rows:
        entry = values.setdefault(
            row["status_text"],
            {"value": row["status_text"], "rows": 0, "counts_in_check": row["counts_in_check"]},
        )
        entry["rows"] += 1
    out["status_values"] = sorted(values.values(), key=lambda v: (-v["rows"], v["value"] or ""))
    ready = preview.status == "ready"
    flagged = [r for r in rows if ready and r.get("flags")]
    imported = {r["index"] for r in flagged if r["flags"] == [{"code": "already_imported"}]}
    needing = [r for r in flagged if r["allowed"]]
    out["counts"] = {
        "rows": len(rows),
        "ready": sum(1 for r in rows if ready and not r.get("flags")),
        "flagged": len(flagged) - len(imported),
        "already_imported": len(imported),
        "not_counted": sum(
            1 for r in rows if not r["counts_in_check"] and r["index"] not in imported
        ),
        "waiting_choice": sum(1 for r in needing if r["choice"] is None),
    }
    out["flagged"] = [
        {
            "index": r["index"],
            "legacy_number": r["legacy_number"] or r.get("legacy_number_file"),
            "full_name": r["full_name"],
            "phone_file": r["phone_file"],
            "phone": r["phone"],
            "family_number_file": r["family_number_file"],
            "status_text": r["status_text"],
            "counts_in_check": r["counts_in_check"],
            "flags": r["flags"],
            "allowed": r["allowed"],
            "choice": r["choice"],
            "corrected_family_number": r["corrected_family_number"],
        }
        for r in flagged
    ]
    return out
