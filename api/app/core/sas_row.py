"""One row of the SAS subscribers export (docs/system.md 1.20 §12.2; specs/015 research R2–R7, R9).

Pure functions, no database: header matching, value cleaning, the username split and tower rule,
the comparison with a stored row, and the flags. A password column is never mapped, so its cells
never become part of a row (research R3). Names and usernames are kept as written (trimmed);
phones go through §8.1, the same helper the check uses. Nothing here logs: rows hold personal
data.
"""

import copy
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.legacy_row import clean_text, parse_timestamp
from app.core.phone import normalize_phone, to_latin_digits

# key → the header text of the SAS export (after `_header_text`).
_HEADERS: dict[str, str] = {
    "sas_id": "id",
    "username": "username",
    "first_name": "firstname",
    "last_name": "lastname",
    "phone": "phone",
    "expiration": "expiration",
    "notes": "notes",
    "parent_name": "parent_name",
    "created_at": "created_at",
    "last_online": "last_online",
    "group_name": "group_name",
}
REQUIRED = ("username", "phone")

# The fields a re-import compares, in this order (research R7). `tower_id` is set by the service
# (rule or mapping) before the comparison.
COMPARED_FIELDS = (
    "sas_id",
    "username",
    "first_name",
    "last_name",
    "phone",
    "phone_file",
    "username_phone",
    "tower_id",
    "expires_at",
    "sas_created_at",
    "last_online_at",
    "group_name",
    "parent_name",
    "notes",
)
_PHONE_FIELDS = frozenset({"phone", "username_phone"})

_SPACES = re.compile(r"\s+")
_PHONE_SEGMENT = re.compile(r"[+0-9\s]+")
_NEVER = re.compile(r"0{4}-0{2}-0{2}.*")


class MissingColumns(Exception):
    def __init__(self, columns: list[str]) -> None:
        super().__init__("missing columns")
        self.columns = columns


def _header_text(text: Any) -> str:
    return _SPACES.sub(" ", str(text or "")).strip().lower()


def is_password_header(text: Any) -> bool:
    return "password" in _header_text(text)


def match_headers(headers: list[Any]) -> dict[str, int]:
    """Column index per known key. A password column (`ct_password` or any header holding
    «password») is never mapped; unknown columns are ignored; missing required ones raise."""
    wanted = {text: key for key, text in _HEADERS.items()}
    found: dict[str, int] = {}
    for index, header in enumerate(headers):
        if is_password_header(header):
            continue
        key = wanted.get(_header_text(header))
        if key is not None and key not in found:
            found[key] = index
    missing = [key for key in REQUIRED if key not in found]
    if missing:
        raise MissingColumns(missing)
    return found


# --- username, prefix, tower (research R4) -----------------------------------------------------


def username_key(value: Any) -> str | None:
    """The re-import key: trimmed, Latin digits, upper-case; empty → None."""
    text = clean_text(value)
    return to_latin_digits(text).upper() if text else None


def split_username(value: Any) -> tuple[str | None, str | None]:
    """(prefix, phone). The phone is the last `-` segment when it is a §8.1 phone; the prefix is
    what comes before it, upper-cased. No phone → (None, None)."""
    text = clean_text(value)
    if text is None:
        return None, None
    text = to_latin_digits(text)
    head, _, last = text.rpartition("-")
    if not _PHONE_SEGMENT.fullmatch(last):
        return None, None
    phone = normalize_phone(last)
    if phone is None:
        return None, None
    prefix = head.strip().upper()
    return (prefix or None), phone


def tower_code_from_prefix(prefix: str) -> str:
    """`RBD-01S` → `RBD01S`: dashes and spaces removed, upper-cased (tower codes are
    `^[A-Z0-9]{2,20}$`, specs/004)."""
    return re.sub(r"[-\s]", "", prefix).upper()


def resolve_tower(
    prefix: str | None,
    towers: Mapping[str, int],
    mappings: Mapping[str, int | None],
) -> tuple[int | None, str]:
    """(tower id or None, source): `rule` (the code exists), `mapping` (saved by the admin, None
    is «بلا برج»), `unmapped` (needs the admin), `none` (no prefix). The rule wins."""
    if prefix is None:
        return None, "none"
    tower = towers.get(tower_code_from_prefix(prefix))
    if tower is not None:
        return tower, "rule"
    if prefix in mappings:
        return mappings[prefix], "mapping"
    return None, "unmapped"


# --- dates (research R6) -----------------------------------------------------------------------


def parse_sas_date(value: Any) -> tuple[datetime | None, bool]:
    """(UTC datetime or None, unreadable). Naive values are Baghdad time. Empty and SAS «never»
    values (`0000-00-00…`) are None and not unreadable."""
    if isinstance(value, datetime):
        return parse_timestamp(value), False
    text = clean_text(value)
    if text is None or _NEVER.fullmatch(to_latin_digits(text)):
        return None, False
    parsed = parse_timestamp(text)
    return parsed, parsed is None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# --- one row -----------------------------------------------------------------------------------


def _flag(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, **details}


def clean_row(index: int, raw: Mapping[str, Any]) -> dict[str, Any]:
    """The cleaned values of one file row (data-model.md › SasPreviewRow, without the kind and
    the cross-row flags). `raw` holds only mapped columns: never a password."""
    username = clean_text(raw.get("username"))
    key = username_key(username)
    prefix, username_phone = split_username(username)
    first_name = clean_text(raw.get("first_name"))
    last_name = clean_text(raw.get("last_name"))
    phone_file = clean_text(raw.get("phone"))
    phone = normalize_phone(phone_file) if phone_file else None
    dates: dict[str, str | None] = {}
    unreadable = False
    for target, source in (
        ("expires_at", "expiration"),
        ("sas_created_at", "created_at"),
        ("last_online_at", "last_online"),
    ):
        parsed, bad = parse_sas_date(raw.get(source))
        dates[target] = _iso(parsed)
        unreadable = unreadable or bad
    info: list[str] = []
    if phone is None and username_phone is None:
        info.append("no_valid_phone")
    if username is not None and username_phone is None:
        info.append("username_no_phone")
    if unreadable:
        info.append("date_unreadable")
    return {
        "index": index,
        "sas_id": clean_text(raw.get("sas_id")),
        "username": username,
        "username_key": key,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": " ".join(part for part in (first_name, last_name) if part),
        "phone_file": phone_file,
        "phone": phone,
        "username_phone": username_phone,
        "prefix": prefix,
        **dates,
        "group_name": clean_text(raw.get("group_name")),
        "parent_name": clean_text(raw.get("parent_name")),
        "notes": clean_text(raw.get("notes")),
        "base_flags": [] if key else [_flag("username_missing")],
        "info": info,
    }


def phones(row: Mapping[str, Any]) -> set[str]:
    """The phones a row holds for the check: the phone column and the username phone (FR-012)."""
    return {p for p in (row.get("phone"), row.get("username_phone")) if p}


# --- comparison with the stored row (research R7) ----------------------------------------------


def diff(stored: Mapping[str, Any] | None, row: Mapping[str, Any]) -> tuple[str, list[str]]:
    """(`new` | `unchanged` | `update`, changed field names in COMPARED_FIELDS order)."""
    if stored is None:
        return "new", []
    changed = [name for name in COMPARED_FIELDS if stored.get(name) != row.get(name)]
    return ("update" if changed else "unchanged"), changed


# --- flags across rows and with stored data (research R9) --------------------------------------


@dataclass(frozen=True)
class Existing:
    """Stored data the flags compare with (loaded by the service)."""

    # username_key → the stored row's COMPARED_FIELDS values plus its `id`.
    stored: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    # phone → [(request number label, upper-case username or None)] of live active requests.
    sijil_phones: Mapping[str, list[tuple[str, str | None]]] = field(default_factory=dict)
    # Upper-case usernames of live active requests (FR-018).
    sijil_usernames: frozenset[str] = frozenset()
    legacy_phones: frozenset[str] = frozenset()


def _request_order(label: str) -> int:
    digits = "".join(c for c in label if c.isdigit())
    return int(digits) if digits else 0


def allowed_choices(flags: list[dict[str, Any]]) -> list[str]:
    if not flags:
        return []
    if any(flag["code"] == "username_missing" for flag in flags):
        return ["skip"]
    return ["import", "skip"]


def compute_flags(rows: list[dict[str, Any]], existing: Existing) -> list[dict[str, Any]]:
    """Copies of the rows with `kind`, `stored_id`, `changed`, `flags`, `info` and `allowed`.
    Choices are kept. The input is not changed; running it again gives the same result."""
    rows = copy.deepcopy(rows)
    by_key: dict[str, list[int]] = defaultdict(list)
    by_phone: dict[str, int] = defaultdict(int)
    for row in rows:
        if row["username_key"]:
            by_key[row["username_key"]].append(row["index"])
        for phone in phones(row):
            by_phone[phone] += 1

    for row in rows:
        key = row["username_key"]
        base_info = row.setdefault("base_info", list(row["info"]))
        stored = existing.stored.get(key) if key else None
        kind, changed = diff(stored, row)
        row["kind"] = kind
        row["changed"] = changed
        row["stored_id"] = stored["id"] if stored else None

        flags = list(row["base_flags"])
        info = list(base_info)
        if key and len(by_key[key]) > 1:
            flags.append(
                _flag("username_dup_file", rows=[i for i in by_key[key] if i != row["index"]])
            )
        held = phones(row)
        if kind == "new" or (kind == "update" and _PHONE_FIELDS & set(changed)):
            labels = {
                label
                for phone in held
                for label, username in existing.sijil_phones.get(phone, [])
                if username != key
            }
            if labels:
                flags.append(_flag("phone_in_sijil", requests=sorted(labels, key=_request_order)))
        if key and key in existing.sijil_usernames:
            info.append("same_username_in_sijil")
        if any(by_phone[phone] > 1 for phone in held):
            info.append("phone_dup_file")
        if held & existing.legacy_phones:
            info.append("phone_in_legacy")
        row["flags"] = flags
        row["info"] = info
        row["allowed"] = allowed_choices(flags)
        row.setdefault("choice", None)
    return rows
