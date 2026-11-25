"""Import of the SAS subscribers export (docs/system.md 1.20 §12.2; specs/015 research R2–R12).

Upload → preview (built in the request: no images, no job) → choices → confirm. The upload is read
in memory and never written to disk; only mapped columns reach a row, so `ct_password` is never
kept anywhere (research R3). Previews live one hour and belong to their uploader. Log lines carry
ids and counts only: a SAS username holds the phone (research R11).
"""

import copy
import logging
import uuid
from collections import defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import sas_row
from app.core.timeutil import utc_now
from app.db import get_sessionmaker
from app.errors import AppError
from app.models import (
    LegacySubscriber,
    Request,
    SasImport,
    SasImportPreview,
    SasSubscriber,
    SasSubscriberChange,
    SasTowerMapping,
    Tower,
    User,
)
from app.models.request import ACTIVE_STATUSES
from app.services import audit_service, legacy_file
from app.services.import_lock import IMPORT_CONFIRM_LOCK

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


def summary(db: Session, preview: SasImportPreview) -> dict[str, Any]:
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
        # Every tower, stopped ones too: a prefix may map to any of them (research R4). Sent here
        # because a `reports` admin may hold no `settings` permission.
        "towers": [
            {"id": t.id, "code": t.code, "name": t.name, "is_active": t.is_active}
            for t in db.scalars(select(Tower).order_by(Tower.code))
        ],
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


# --- choices (research R9; FR-006) ---------------------------------------------------------------


def _effective_mappings(db: Session, prefixes: list[dict[str, Any]]) -> dict[str, int | None]:
    """Saved mappings, overridden by the ones chosen in this preview."""
    return _mappings(db) | {e["prefix"]: e["tower_id"] for e in prefixes if e["chosen"]}


def _apply_towers(
    rows: list[dict[str, Any]], towers: dict[str, int], mappings: dict[str, int | None]
) -> None:
    for row in rows:
        row["tower_id"], row["tower_source"] = sas_row.resolve_tower(
            row["prefix"], towers, mappings
        )


def _check_repeated_usernames(rows: list[dict[str, Any]]) -> None:
    """At most one row per username may be imported: the username is the key (research R9)."""
    seen: set[str] = set()
    for row in rows:
        if row["choice"] != "import" or not row["username_key"]:
            continue
        if row["username_key"] in seen:
            raise AppError("choice_not_allowed", 422)
        seen.add(row["username_key"])


def set_choices(
    db: Session,
    user: User,
    preview_id: uuid.UUID,
    choices: list[dict[str, Any]],
    prefixes: list[dict[str, Any]],
) -> SasImportPreview:
    """«استيراد» / «تخطي» per flagged row, and a tower (or «بلا برج») per listed prefix. «تخطي
    للكل» is the same call with skip for every row of a group; any row can be changed afterwards."""
    preview = get_preview(db, user, preview_id)
    rows = copy.deepcopy(preview.rows)
    entries = copy.deepcopy(preview.prefixes)
    towers = _towers(db)
    by_prefix = {entry["prefix"]: entry for entry in entries}
    known = set(towers.values())
    for item in prefixes:
        entry = by_prefix.get(item["prefix"])
        if entry is None:
            raise AppError("choice_not_allowed", 422)
        if item["tower_id"] is not None and item["tower_id"] not in known:
            raise AppError("tower_not_found", 422)
        entry["tower_id"] = item["tower_id"]
        entry["chosen"] = True
    by_index = {row["index"]: row for row in rows}
    for item in choices:
        row = by_index.get(item["index"])
        if row is None or not row["flags"] or item["choice"] not in row["allowed"]:
            raise AppError("choice_not_allowed", 422)
        row["choice"] = item["choice"]
    _apply_towers(rows, towers, _effective_mappings(db, entries))
    rows = flag(db, rows)
    _check_repeated_usernames(rows)
    preview.rows = rows
    preview.prefixes = entries
    db.commit()
    return preview


# --- confirmation (research R10, R12; FR-006–FR-010) ---------------------------------------------


def _revalidate(
    db: Session, preview: SasImportPreview
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Towers and flags against what is stored now. A row whose flags changed and that needs a
    choice loses its choice, and a prefix no longer resolved joins the table; then the
    confirmation is refused with the updated preview (research R12)."""
    old = {row["index"]: row["flags"] for row in preview.rows}
    rows = copy.deepcopy(preview.rows)
    entries = copy.deepcopy(preview.prefixes)
    _apply_towers(rows, _towers(db), _effective_mappings(db, entries))
    listed = {entry["prefix"] for entry in entries}
    changed = False
    unmapped = {row["prefix"] for row in rows if row["tower_source"] == "unmapped"}
    for prefix in sorted(unmapped - listed):
        entries.append(
            {
                "prefix": prefix,
                "rows": sum(1 for row in rows if row["prefix"] == prefix),
                "tower_id": None,
                "from_previous": False,
                "chosen": False,
            }
        )
        changed = True
    rows = flag(db, rows)
    for row in rows:
        if row["flags"] != old[row["index"]] and row["allowed"]:
            row["choice"] = None
            changed = True
    if changed:
        preview.rows = rows
        preview.prefixes = entries
        db.commit()
        raise AppError(
            "preview_changed", 409, extra={"preview": jsonable_encoder(summary(db, preview))}
        )
    waiting = [r["index"] for r in rows if r["flags"] and r["allowed"] and not r["choice"]]
    waiting_prefixes = [entry["prefix"] for entry in entries if not entry["chosen"]]
    if waiting or waiting_prefixes:
        raise AppError(
            "preview_choices_missing",
            409,
            extra={"indexes": waiting, "prefixes": waiting_prefixes},
        )
    return rows, entries


def _importing(row: dict[str, Any]) -> bool:
    return not row["flags"] or row["choice"] == "import"


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _columns(row: dict[str, Any]) -> dict[str, Any]:
    """The `sas_subscribers` values of a preview row (data-model.md › sas_subscribers)."""
    values = {name: row[name] for name in sas_row.COMPARED_FIELDS}
    for name in ("expires_at", "sas_created_at", "last_online_at"):
        values[name] = _dt(values[name])
    return values | {
        "username_key": row["username_key"],
        "full_name": row["full_name"],
        "tower_prefix": row["prefix"],
    }


def _stored_by_id(db: Session, ids: list[int]) -> dict[int, SasSubscriber]:
    found: dict[int, SasSubscriber] = {}
    for chunk in _chunks(ids):
        for subscriber in db.scalars(select(SasSubscriber).where(SasSubscriber.id.in_(chunk))):
            found[subscriber.id] = subscriber
    return found


def _save_mappings(
    db: Session, user: User, record: SasImport, entries: list[dict[str, Any]]
) -> int:
    """Saves each chosen prefix that is new or whose tower changed; returns how many."""
    saved = 0
    for entry in entries:
        if not entry["chosen"]:
            continue
        mapping = db.get(SasTowerMapping, entry["prefix"])
        if mapping is not None and mapping.tower_id == entry["tower_id"]:
            continue
        if mapping is None:
            mapping = SasTowerMapping(prefix=entry["prefix"])
            db.add(mapping)
        mapping.tower_id = entry["tower_id"]
        mapping.set_by = user.id
        mapping.set_at = utc_now()
        mapping.import_id = record.id
        saved += 1
    return saved


def _mark_missing(
    db: Session, record: SasImport, rows: list[dict[str, Any]], importing: list[dict[str, Any]]
) -> None:
    """«غير موجود في آخر ملف» (FR-022): a stored row whose username is not in this file is marked
    once (the first import that misses it) and keeps counting in the check; a marked row that this
    import holds again is cleared. Re-computed here, so a row another import added meanwhile is
    judged too. A skipped row is in the file: it is neither marked nor cleared."""
    in_file = {row["username_key"] for row in rows if row["username_key"]}
    now = utc_now()
    for subscriber_id, key in db.execute(
        select(SasSubscriber.id, SasSubscriber.username_key).where(
            SasSubscriber.missing_since.is_(None)
        )
    ).all():
        if key not in in_file:
            subscriber = db.get(SasSubscriber, subscriber_id)
            subscriber.missing_since = now
            subscriber.missing_import_id = record.id
            record.missing_marked += 1
    held = {row["stored_id"] for row in importing if row["stored_id"] is not None}
    for chunk in _chunks(held):
        for subscriber in db.scalars(
            select(SasSubscriber).where(
                SasSubscriber.id.in_(chunk), SasSubscriber.missing_since.is_not(None)
            )
        ):
            subscriber.missing_since = None
            subscriber.missing_import_id = None
            record.missing_cleared += 1


def confirm(db: Session, user: User, preview_id: uuid.UUID) -> dict[str, Any]:
    """Add the new rows, update the changed ones (each with a change row), save the mappings and
    one audit entry, in one transaction; on any failure nothing is saved and the preview stays
    (SC-007). Returns the `SasImportSummary`."""
    db.execute(select(func.pg_advisory_xact_lock(IMPORT_CONFIRM_LOCK)))
    preview = get_preview(db, user, preview_id)
    rows, entries = _revalidate(db, preview)

    importing = [row for row in rows if _importing(row)]
    skipped = [row for row in rows if row["flags"] and row["choice"] == "skip"]
    record = SasImport(
        created_by=user.id,
        file_name=preview.file_name,
        rows_total=len(rows),
        added=0,
        updated=0,
        unchanged=0,
        skipped=len(skipped),
        missing_marked=0,
        missing_cleared=0,
        without_phone=0,
        prefixes_mapped=0,
    )
    try:
        db.add(record)
        db.flush()
        updates = [row["stored_id"] for row in importing if row["kind"] == "update"]
        stored = _stored_by_id(db, updates)
        now = utc_now()
        for done, row in enumerate(importing, start=1):
            if row["kind"] == "new":
                db.add(
                    SasSubscriber(
                        **_columns(row), first_import_id=record.id, last_import_id=record.id
                    )
                )
                record.added += 1
            elif row["kind"] == "update":
                subscriber = stored[row["stored_id"]]
                before = stored_values(subscriber)
                for name, value in _columns(row).items():
                    setattr(subscriber, name, value)
                subscriber.last_import_id = record.id
                subscriber.updated_at = now
                db.add(
                    SasSubscriberChange(
                        import_id=record.id,
                        sas_subscriber_id=subscriber.id,
                        before={name: before[name] for name in row["changed"]},
                        after={name: row[name] for name in row["changed"]},
                    )
                )
                record.updated += 1
            else:
                record.unchanged += 1
            record.without_phone += not sas_row.phones(row)
            if done % CHUNK == 0:
                db.flush()
        db.flush()
        _mark_missing(db, record, rows, importing)
        record.prefixes_mapped = _save_mappings(db, user, record, entries)
        counts = {
            "rows": record.rows_total,
            "added": record.added,
            "updated": record.updated,
            "unchanged": record.unchanged,
            "skipped": record.skipped,
            "missing_marked": record.missing_marked,
            "missing_cleared": record.missing_cleared,
            "without_phone": record.without_phone,
            "prefixes_mapped": record.prefixes_mapped,
        }
        # Counts only: no username, phone or name (a SAS username holds the phone; FR-009).
        audit_service.record(
            db,
            actor_id=user.id,
            action="sas.imported",
            entity_type="sas_import",
            entity_id=record.id,
            after={"file_name": record.file_name, **counts},
        )
        db.delete(preview)
        db.commit()
    except Exception:
        db.rollback()
        raise
    log.info(
        "sas import confirmed import=%s added=%d updated=%d skipped=%d",
        record.id,
        record.added,
        record.updated,
        record.skipped,
    )
    return {
        "import_id": record.id,
        **counts,
        "skipped_rows": [{"index": row["index"], "sas_id": row["sas_id"]} for row in skipped],
    }
