"""Import of the SAS subscribers export (docs/system.md 1.20 §12.2; specs/015 research R2–R12).

Upload → preview (built in the request: no images, no job) → choices → confirm. The upload is read
in memory and never written to disk; only mapped columns reach a row, so `ct_password` is never
kept anywhere (research R3). Previews live one hour and belong to their uploader. Log lines carry
ids and counts only: a SAS username holds the phone (research R11).
"""

import logging
import uuid
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import sas_row
from app.core.timeutil import utc_now
from app.db import get_sessionmaker
from app.errors import AppError
from app.models import (
    LegacySubscriber,
    Request,
    SasImportPreview,
    SasSubscriber,
    SasTowerMapping,
    Tower,
    User,
)
from app.models.request import ACTIVE_STATUSES
from app.services import legacy_file

log = logging.getLogger(__name__)

PREVIEW_TTL = timedelta(hours=1)
CHUNK = 1000

# The informational counts of the preview (contracts/api.md › SasPreview.counts).
INFO_COUNTS = (
    "same_username_in_sijil",
    "no_valid_phone",
    "username_no_phone",
    "date_unreadable",
    "phone_dup_file",
    "phone_in_legacy",
)


def _chunks(values: Iterable[Any]) -> Iterator[list[Any]]:
    items = list(values)
    for start in range(0, len(items), CHUNK):
        yield items[start : start + CHUNK]


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def stored_values(subscriber: SasSubscriber) -> dict[str, Any]:
    """A stored row in the representation of a preview row (research R7)."""
    values = {name: getattr(subscriber, name) for name in sas_row.COMPARED_FIELDS}
    for name in ("expires_at", "sas_created_at", "last_online_at"):
        values[name] = _iso(values[name])
    return values | {"id": subscriber.id}


# --- stored data the flags compare with (research R7, R9) ----------------------------------------


def load_existing(db: Session, rows: list[dict[str, Any]]) -> sas_row.Existing:
    keys = {row["username_key"] for row in rows if row["username_key"]}
    phones = set().union(*(sas_row.phones(row) for row in rows)) if rows else set()

    stored: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(keys):
        for subscriber in db.scalars(
            select(SasSubscriber).where(SasSubscriber.username_key.in_(chunk))
        ):
            stored[subscriber.username_key] = stored_values(subscriber)

    live = (Request.status.in_(ACTIVE_STATUSES), Request.deleted_at.is_(None))
    sijil_phones: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for chunk in _chunks(phones):
        for number, phone, username in db.execute(
            select(Request.number, Request.phone, Request.username).where(
                Request.phone.in_(chunk), *live
            )
        ):
            sijil_phones[phone].append((f"T3C-{number}", username.upper() if username else None))
    sijil_usernames: set[str] = set()
    for chunk in _chunks(keys):
        sijil_usernames.update(
            db.scalars(
                select(func.upper(Request.username)).where(
                    func.upper(Request.username).in_(chunk), *live
                )
            )
        )
    legacy_phones: set[str] = set()
    for chunk in _chunks(phones):
        legacy_phones.update(
            db.scalars(
                select(LegacySubscriber.phone).where(
                    LegacySubscriber.phone.in_(chunk), LegacySubscriber.counts_in_check
                )
            )
        )
    return sas_row.Existing(
        stored=stored,
        sijil_phones=dict(sijil_phones),
        sijil_usernames=frozenset(sijil_usernames),
        legacy_phones=frozenset(legacy_phones),
    )


# --- towers (research R4) ------------------------------------------------------------------------


def _towers(db: Session) -> dict[str, int]:
    return {code: tower_id for code, tower_id in db.execute(select(Tower.code, Tower.id))}


def _mappings(db: Session) -> dict[str, int | None]:
    return {
        prefix: tower_id
        for prefix, tower_id in db.execute(select(SasTowerMapping.prefix, SasTowerMapping.tower_id))
    }


def _resolve_towers(
    rows: list[dict[str, Any]], towers: dict[str, int], mappings: dict[str, int | None]
) -> list[dict[str, Any]]:
    """Sets `tower_id` / `tower_source` on every row and returns the mapping table: one entry per
    prefix with no rule match, pre-filled from a saved mapping (contracts/api.md › prefixes)."""
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        tower_id, source = sas_row.resolve_tower(row["prefix"], towers, mappings)
        row["tower_id"] = tower_id
        row["tower_source"] = source
        if source in ("mapping", "unmapped"):
            counts[row["prefix"]] += 1
    return [
        {
            "prefix": prefix,
            "rows": counts[prefix],
            "tower_id": mappings.get(prefix),
            "from_previous": prefix in mappings,
            "chosen": prefix in mappings,
        }
        for prefix in sorted(counts)
    ]


# --- upload --------------------------------------------------------------------------------------


def _clean_file_name(name: str | None) -> str:
    return (Path(name or "").name or "file")[:200]


def _read_rows(data: bytes) -> list[dict[str, Any]]:
    """Cleaned rows built from the mapped columns only; the full cell lists are dropped here, so a
    password cell never leaves this function (research R3)."""
    headers, body = legacy_file.read_table(
        data, max_bytes=legacy_file.SAS_MAX_FILE_BYTES, max_rows=legacy_file.SAS_MAX_ROWS
    )
    try:
        columns = sas_row.match_headers(headers)
    except sas_row.MissingColumns as missing:
        raise AppError(
            "import_columns_missing",
            422,
            message="الملف ينقصه عمود: " + "، ".join(missing.columns),
            extra={"columns": missing.columns},
        ) from None
    rows = []
    for offset, cells in enumerate(body):
        raw = {key: cells[i] if i < len(cells) else None for key, i in columns.items()}
        rows.append(sas_row.clean_row(offset + 2, raw))  # file row number; the header is row 1
    del body
    return rows


def _stored_keys(db: Session) -> dict[str, int]:
    return {
        key: subscriber_id
        for key, subscriber_id in db.execute(select(SasSubscriber.username_key, SasSubscriber.id))
    }


def flag(db: Session, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kinds and flags against what is stored now; choices are carried over."""
    return sas_row.compute_flags(rows, load_existing(db, rows))


def sweep_expired(db: Session) -> int:
    result = db.execute(delete(SasImportPreview).where(SasImportPreview.expires_at <= utc_now()))
    db.commit()
    return result.rowcount or 0


def sweep_at_startup() -> None:
    db = get_sessionmaker()()
    try:
        removed = sweep_expired(db)
        if removed:
            log.info("sas previews swept expired=%d", removed)
    except Exception:
        log.exception("sweeping sas previews failed")
    finally:
        db.close()


def create_preview(db: Session, user: User, file_name: str | None, data: bytes) -> SasImportPreview:
    rows = _read_rows(data)
    prefixes = _resolve_towers(rows, _towers(db), _mappings(db))
    rows = flag(db, rows)
    in_file = {row["username_key"] for row in rows if row["username_key"]}
    missing_ids = sorted(sid for key, sid in _stored_keys(db).items() if key not in in_file)

    sweep_expired(db)
    db.execute(delete(SasImportPreview).where(SasImportPreview.created_by == user.id))
    preview = SasImportPreview(
        id=uuid.uuid4(),
        created_by=user.id,
        expires_at=utc_now() + PREVIEW_TTL,
        file_name=_clean_file_name(file_name),
        rows=rows,
        prefixes=prefixes,
        missing_ids=missing_ids,
    )
    db.add(preview)
    db.commit()
    log.info(
        "sas preview created preview=%s rows=%d flagged=%d prefixes=%d",
        preview.id,
        len(rows),
        sum(1 for row in rows if row["flags"]),
        len(prefixes),
    )
    return preview


def get_preview(db: Session, user: User, preview_id: uuid.UUID) -> SasImportPreview:
    sweep_expired(db)
    preview = db.get(SasImportPreview, preview_id)
    if preview is None or preview.created_by != user.id:
        raise AppError("preview_not_found", 404)
    db.refresh(preview)
    return preview


def cancel(db: Session, user: User, preview_id: uuid.UUID) -> None:
    db.delete(get_preview(db, user, preview_id))
    db.commit()


# --- the body ------------------------------------------------------------------------------------


def summary(preview: SasImportPreview) -> dict[str, Any]:
    """The `SasPreview` body of contracts/api.md: counts, mapping table, flagged rows only."""
    rows = preview.rows
    flagged = [row for row in rows if row["flags"]]
    kinds: dict[str, int] = defaultdict(int)
    info: dict[str, int] = defaultdict(int)
    for row in rows:
        kinds[row["kind"]] += 1
        for code in row["info"]:
            info[code] += 1
    counts = {
        "rows": len(rows),
        "new": kinds["new"],
        "update": kinds["update"],
        "unchanged": kinds["unchanged"],
        "missing_from_file": len(preview.missing_ids),
        "flagged": len(flagged),
        "waiting_choice": sum(1 for row in flagged if row["choice"] is None),
    } | {code: info[code] for code in INFO_COUNTS}
    return {
        "id": preview.id,
        "file_name": preview.file_name,
        "expires_at": preview.expires_at,
        "counts": counts,
        "prefixes": preview.prefixes,
        "waiting_prefixes": sum(1 for entry in preview.prefixes if not entry["chosen"]),
        "flagged": [
            {
                "index": row["index"],
                "sas_id": row["sas_id"],
                "username": row["username"],
                "full_name": row["full_name"],
                "phone": row["phone"],
                "username_phone": row["username_phone"],
                "kind": row["kind"],
                "flags": row["flags"],
                "allowed": row["allowed"],
                "choice": row["choice"],
            }
            for row in flagged
        ],
    }
