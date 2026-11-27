"""«المشتركون» search across Sijil requests, legacy and SAS subscribers (docs/system.md v1.24 §10
item 4; specs/018 research R3, R4, R6).

One capped query per source, each on its own indexed keys; the rows are merged newest first and
paged. Names are folded on read (legacy and SAS keep names as written, §12) with the same folding
as `core.arabic_name.fold_arabic`. Rows carry no identity number (research R7). Who may search by
an identity kind is decided by the router, before this runs.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.arabic_name import FOLD_FROM, FOLD_TO, REMOVED_CHARACTERS
from app.core.subscriber_search import Term
from app.models import LegacySubscriber, Request, SasSubscriber, Tower

# Every kind each source can answer (data-model.md › Derived: search term).
_SOURCE_KINDS = {
    "sijil": {"number", "national_id", "phone", "family", "username", "name"},
    "legacy": {"legacy_number", "phone", "family", "name"},
    "sas": {"phone", "username", "name"},
}


@dataclass(frozen=True)
class Row:
    source: str
    ref: str
    number_label: str | None
    legacy_number: str | None
    full_name: str | None
    tower_name: str | None
    tower_code: str | None
    phone: str | None
    status: str | None
    registered_at: datetime | None
    deleted: bool = False


def folded(column):
    """SQL mirror of `fold_arabic`: remove diacritics, tatweel and marks; fold أإآٱ/ة/ى; collapse
    spaces."""
    stripped = func.regexp_replace(column, f"[{REMOVED_CHARACTERS}]", "", "g")
    return func.btrim(
        func.regexp_replace(func.translate(stripped, FOLD_FROM, FOLD_TO), r"\s+", " ", "g")
    )


def _name_match(column, value: str):
    # `value` is Arabic letters and spaces only (core.subscriber_search.classify).
    return folded(column).contains(value, autoescape=True)


# --- per source ----------------------------------------------------------------------------------


def _sijil_where(term: Term):
    v = term.value
    if term.kind == "number":
        return [Request.number == v]  # deleted ones too: they are found by number only (§7.4)
    live = Request.deleted_at.is_(None)
    if term.kind == "national_id":
        return [live, Request.national_id == v]
    if term.kind == "phone":
        return [live, Request.phone == v]
    if term.kind == "family":
        return [live, Request.family_key == v]
    if term.kind == "username":
        return [live, func.upper(Request.username) == v]
    return [live, _name_match(Request.full_name, v)]


def _sijil_row(r: Request) -> Row:
    if r.is_deleted:
        return Row(
            "sijil", str(r.id), r.number_label, None, None, None, None, None, None, None, True
        )
    return Row(
        "sijil",
        str(r.id),
        r.number_label,
        None,
        r.full_name,
        r.tower_name,
        r.tower_code,
        r.phone,
        r.status,
        r.submitted_at,
    )


def _legacy_where(term: Term):
    v = term.value
    if term.kind == "legacy_number":
        return [func.upper(LegacySubscriber.legacy_number) == v]
    if term.kind == "phone":
        return [LegacySubscriber.phone == v]
    if term.kind == "family":
        return [LegacySubscriber.family_key == v]
    return [_name_match(LegacySubscriber.full_name, v)]


def _legacy_time():
    return func.coalesce(LegacySubscriber.form_submitted_at, LegacySubscriber.created_at)


def _legacy_row(s: LegacySubscriber) -> Row:
    return Row(
        "legacy",
        str(s.id),
        None,
        s.legacy_number,
        s.full_name,
        None,
        None,
        s.phone,
        s.status_text,
        s.form_submitted_at or s.created_at,
    )


def _sas_where(term: Term):
    v = term.value
    if term.kind == "phone":
        return [(SasSubscriber.phone == v) | (SasSubscriber.username_phone == v)]
    if term.kind == "username":
        return [SasSubscriber.username_key == v]
    return [_name_match(SasSubscriber.full_name, v)]


def _sas_time():
    return func.coalesce(SasSubscriber.sas_created_at, SasSubscriber.created_at)


def _sas_row(s: SasSubscriber, tower: Tower | None) -> Row:
    return Row(
        "sas",
        str(s.id),
        None,
        None,
        s.full_name,
        tower.name if tower else None,
        tower.code if tower else s.tower_prefix,
        s.phone or s.username_phone,
        s.expires_at.date().isoformat() if s.expires_at else None,
        s.sas_created_at or s.created_at,
    )


# --- merge ---------------------------------------------------------------------------------------


def _count(db: Session, model, where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


def search(db: Session, term: Term, offset: int, limit: int) -> tuple[list[Row], int]:
    """The page of rows and the total (research R4). Each source returns at most
    `offset + limit` rows, newest first; the merge keeps the global order."""
    cap = offset + limit
    rows: list[Row] = []
    total = 0
    if term.kind in _SOURCE_KINDS["sijil"]:
        where = _sijil_where(term)
        total += _count(db, Request, where)
        found = db.scalars(
            select(Request)
            .where(*where)
            .order_by(Request.submitted_at.desc(), Request.id.desc())
            .limit(cap)
        ).all()
        rows += [_sijil_row(r) for r in found]
    if term.kind in _SOURCE_KINDS["legacy"]:
        where = _legacy_where(term)
        total += _count(db, LegacySubscriber, where)
        found = db.scalars(
            select(LegacySubscriber)
            .where(*where)
            .order_by(_legacy_time().desc(), LegacySubscriber.id.desc())
            .limit(cap)
        ).all()
        rows += [_legacy_row(s) for s in found]
    if term.kind in _SOURCE_KINDS["sas"]:
        where = _sas_where(term)
        total += _count(db, SasSubscriber, where)
        found = db.execute(
            select(SasSubscriber, Tower)
            .outerjoin(Tower, Tower.id == SasSubscriber.tower_id)
            .where(*where)
            .order_by(_sas_time().desc(), SasSubscriber.id.desc())
            .limit(cap)
        ).all()
        rows += [_sas_row(s, t) for s, t in found]

    floor = datetime.min.replace(tzinfo=None)

    def key(row: Row):
        at = row.registered_at
        return (at.replace(tzinfo=None) if at else floor, row.source, int(row.ref))

    rows.sort(key=key, reverse=True)
    return rows[offset:cap], total


# The row of each source, shared with the file's linked records (services/subscriber_file.py).
request_row = _sijil_row
legacy_row = _legacy_row
sas_row = _sas_row
