"""Running card readings (specs/006 research R5; data-model.md › card_readings).

Flow:
1. An image upload calls `mark_pending` inside its own transaction (that side → `pending`).
2. After the upload commits, `queue_if_ready` submits `run` when both sides have an image.
3. `run` (a worker thread with its own DB session) sends each pending side to the reader, logs
   the access (`image_access_log.purpose = 'ocr'`, analysis C1), stores the raw answer and the
   evaluated side, and drops results for images replaced meanwhile.
4. `sweep_stale` turns readings stuck past the 60-second limit into `failed/timeout`.

Logs carry only the draft id, side, state, reason and timing: never card text (FR-019).
"""

import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.card_reading import READING_LIMIT_S
from app.core.national_id import normalize_national_id
from app.core.timeutil import utc_now
from app.db import get_sessionmaker
from app.models import CardReading, Draft, DraftImage, ImageAccessLog
from app.schemas.drafts import (
    CardFieldMarkOut,
    CardReadingOut,
    CardReadingSideOut,
    NationalIdCheckOut,
)
from app.services import image_store
from app.services.card_reader import CardReader, ReaderError, get_card_reader
from app.services.card_reading_rules import evaluate_side

log = logging.getLogger("sijil.card_reading")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="card-reading")


def _submit_to_pool(draft_id: uuid.UUID) -> None:
    _executor.submit(_run_safely, draft_id)


# Replaced in tests by a function that runs `run(draft_id, session=<test session>)` at once.
submit: Callable[[uuid.UUID], None] = _submit_to_pool


def _run_safely(draft_id: uuid.UUID) -> None:
    try:
        run(draft_id)
    except Exception:  # a worker must never die silently; no card data in the message
        log.exception("card reading job failed for draft %s", draft_id)


# --- called from the upload ---------------------------------------------------------------------


def mark_pending(
    draft: Draft, side: str, file_name: str, client_id: uuid.UUID | None
) -> CardReading:
    """That side's reading now belongs to the new image and waits (inside the upload's
    transaction). Raw and evaluated results of the old image are cleared."""
    reading = next((r for r in draft.card_readings if r.side == side), None)
    if reading is None:
        reading = CardReading(side=side, image_file_name=file_name)
        draft.card_readings.append(reading)
    reading.image_file_name = file_name
    reading.state = "pending"
    reading.reason = None
    reading.raw = None
    reading.result = None
    reading.queued_by_client = client_id
    reading.started_at = None
    reading.finished_at = None
    reading.duration_ms = None
    reading.updated_at = utc_now()
    return reading


def ready_to_read(draft: Draft) -> bool:
    """Both sides have an image and at least one side waits (FR-001)."""
    sides = {image.side for image in draft.images}
    return sides >= {"front", "back"} and any(r.state == "pending" for r in draft.card_readings)


def queue_if_ready(draft: Draft) -> bool:
    if ready_to_read(draft):
        submit(draft.id)
        return True
    return False


# --- the job ------------------------------------------------------------------------------------


def _start(db: Session, draft_id: uuid.UUID) -> list[tuple[int, str, str]]:
    """Mark the pending sides `running` and log the access; returns (id, side, file name)."""
    draft = db.get(Draft, draft_id, with_for_update=True)
    if draft is None:
        return []
    images = {image.side: image for image in draft.images}
    if set(images) < {"front", "back"}:
        db.rollback()
        return []
    now = utc_now()
    started: list[tuple[int, str, str]] = []
    for reading in draft.card_readings:
        image = images.get(reading.side)
        if reading.state != "pending" or image is None:
            continue
        if image.file_name != reading.image_file_name:
            continue
        reading.state = "running"
        reading.started_at = now
        reading.updated_at = now
        db.add(
            ImageAccessLog(
                user_id=image.uploaded_by,
                image_id=image.id,
                draft_id=draft.id,
                side=image.side,
                purpose="ocr",
            )
        )
        started.append((reading.id, reading.side, reading.image_file_name))
    db.commit()
    return started


def _finish(
    db: Session,
    reading_id: int,
    file_name: str,
    *,
    state: str,
    reason: str | None,
    raw: dict | None = None,
    result: dict | None = None,
    duration_ms: int | None = None,
) -> bool:
    """Store the outcome unless the image was replaced meanwhile (US6-3)."""
    reading = db.get(CardReading, reading_id, with_for_update=True)
    if reading is None or reading.image_file_name != file_name or reading.state != "running":
        db.rollback()
        return False
    now = utc_now()
    reading.state = state
    reading.reason = reason
    reading.raw = raw
    reading.result = result
    reading.duration_ms = duration_ms
    reading.finished_at = now
    reading.updated_at = now
    db.commit()
    return True


def run(
    draft_id: uuid.UUID,
    session: Session | None = None,
    reader: CardReader | None = None,
    limit_s: float = READING_LIMIT_S,
) -> None:
    """Read every pending side of a draft whose two images are present (R5)."""
    db = session or get_sessionmaker()()
    reader = reader or get_card_reader()
    deadline = time.monotonic() + limit_s
    try:
        for reading_id, side, file_name in _start(db, draft_id):
            started = time.monotonic()
            if started > deadline:
                _finish(db, reading_id, file_name, state="failed", reason="timeout")
                continue
            try:
                image = image_store.open_path(file_name).read_bytes()
                raw = reader.read(image, side)
            except ReaderError as exc:
                _finish(db, reading_id, file_name, state="failed", reason=exc.reason)
                log.warning("card reading %s/%s failed: %s", draft_id, side, exc.reason)
                continue
            except FileNotFoundError:
                # The image was replaced or the draft deleted while waiting: nothing to store.
                db.rollback()
                continue
            except Exception as exc:
                _finish(db, reading_id, file_name, state="failed", reason="error")
                log.warning("card reading %s/%s error: %s", draft_id, side, type(exc).__name__)
                continue
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if time.monotonic() > deadline:
                _finish(
                    db,
                    reading_id,
                    file_name,
                    state="failed",
                    reason="timeout",
                    duration_ms=elapsed_ms,
                )
                continue
            outcome = evaluate_side(raw, side)
            _finish(
                db,
                reading_id,
                file_name,
                state=outcome.state,
                reason=outcome.reason,
                raw=raw,
                result=outcome.result,
                duration_ms=elapsed_ms,
            )
            log.info(
                "card reading %s/%s: %s %s (%d ms)",
                draft_id,
                side,
                outcome.state,
                outcome.reason or "",
                elapsed_ms,
            )
    finally:
        if session is None:
            db.close()


# --- what the page sees (research R11: never the raw result) ---------------------------------


def reading_out(draft: Draft) -> CardReadingOut:
    by_side = {reading.side: reading for reading in draft.card_readings}
    has_image = {image.side for image in draft.images}

    def side_out(side: str) -> CardReadingSideOut | None:
        reading = by_side.get(side)
        if reading is None or side not in has_image:
            return None
        surname_empty = None
        if side == "front" and reading.state == "done" and reading.result:
            surname_empty = bool(reading.result.get("surname_empty"))
        return CardReadingSideOut(
            state=reading.state,
            reason=reading.reason,
            finished_at=reading.finished_at,
            surname_empty=surname_empty,
        )

    return CardReadingOut(front=side_out("front"), back=side_out("back"))


def card_fields_out(draft: Draft) -> dict[str, CardFieldMarkOut]:
    return {
        field: CardFieldMarkOut.model_validate(mark)
        for field, mark in (draft.card_fields or {}).items()
    }


def national_id_check_out(draft: Draft) -> NationalIdCheckOut | None:
    check = draft.national_id_check
    if not check or not check.get("mrz"):
        return None
    current = normalize_national_id(draft.national_id)
    mismatch = current != check["mrz"]
    confirmed = (
        mismatch
        and check.get("confirmed_value") not in (None, "")
        and (check.get("confirmed_value") == draft.national_id)
    )
    return NationalIdCheckOut(mrz=check["mrz"], mismatch=mismatch, confirmed=confirmed)


# --- stale readings -----------------------------------------------------------------------------


def sweep_stale(
    db: Session, draft_id: uuid.UUID | None = None, limit_s: float = READING_LIMIT_S
) -> int:
    """`running` past the limit, or `pending` past the limit while both images exist (the job
    was lost, e.g. an api restart), become `failed/timeout`. Returns how many rows changed."""
    cutoff = utc_now() - timedelta(seconds=limit_s)
    stuck_running = (CardReading.state == "running") & (CardReading.started_at < cutoff)
    stuck_pending = (CardReading.state == "pending") & (CardReading.updated_at < cutoff)
    stmt = update(CardReading).where(stuck_running | stuck_pending)
    if draft_id is not None:
        stmt = stmt.where(CardReading.draft_id == draft_id)
    # A pending side whose other side has no image is waiting for the marketer, not stuck.
    stmt = stmt.where(
        select(DraftImage.id)
        .where(DraftImage.draft_id == CardReading.draft_id)
        .where(DraftImage.side != CardReading.side)
        .exists()
    )
    now = utc_now()
    result = db.execute(
        stmt.values(
            state="failed", reason="timeout", finished_at=now, updated_at=now
        ).execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount or 0


def sweep_at_startup() -> None:
    db = get_sessionmaker()()
    try:
        changed = sweep_stale(db)
        if changed:
            log.warning("marked %d stale card readings as timed out", changed)
    except Exception:
        log.exception("sweeping stale card readings failed")
    finally:
        db.close()
