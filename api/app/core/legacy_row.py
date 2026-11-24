"""One row of the legacy Google Form file (docs/system.md 1.19 §12.1; specs/014 research R3, R5).

Pure functions, no database: header matching, value cleaning, and the flags a row carries on its
own. Flags that compare rows with each other or with stored data come from `compute_flags`
(research R6). Values are kept as written where §12.1 says so (names, family number); phones go
through §8.1 and family numbers get their §6.2 comparison key, the same helpers the check uses.
Nothing here logs: rows hold personal data.
"""

import copy
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any

from app.core.family_key import family_key
from app.core.phone import normalize_phone, to_latin_digits
from app.core.timeutil import BAGHDAD

# key → accepted header texts (after `_header_text`).
_HEADERS: dict[str, tuple[str, ...]] = {
    "timestamp": ("طابع زمني",),
    "first_name": ("الاسم الاول",),
    "second_name": ("الاسم الثاني",),
    "third_name": ("الاسم الثالث",),
    "mother_name": ("اسم الام",),
    "mother_father_name": ("اسم اب الام",),
    "birth_date": ("تاريخ الميلاد",),
    "family_number": ("الرقم العائلي",),
    "phone": ("رقم الهاتف",),
    # «البطافة» is the typo of the real form; both spellings are accepted.
    "front_image": ("صورة البطافة الموحدة الوجه", "صورة البطاقة الموحدة الوجه"),
    "back_image": ("صورة البطاقة الموحدة الظهر", "صورة البطافة الموحدة الظهر"),
    "email_1": ("عنوان البريد الالكتروني",),
    "email_2": ("البريد الالكتروني",),
    "legacy_number": ("id",),
    "status": ("الحالة",),
}
# Required columns with the name the admin sees when one is missing (research R4).
REQUIRED: dict[str, str] = {
    "first_name": "الاسم الاول",
    "family_number": "الرقم العائلي",
    "phone": "رقم الهاتف",
    "legacy_number": "ID",
}
EXTRA_KEYS = ("mother_name", "mother_father_name", "birth_date", "email_1", "email_2")
EXCLUDED_STATUSES = frozenset({"ملغي", "مرفوض"})
FAMILY_KEY_LENGTH = 18

_SPACES = re.compile(r"\s+")
_HAMZA = str.maketrans("أإآ", "ااا")


class MissingColumns(Exception):
    def __init__(self, columns: list[str]) -> None:
        super().__init__("missing columns")
        self.columns = columns


def _header_text(text: Any) -> str:
    return _SPACES.sub(" ", str(text or "")).strip().translate(_HAMZA).lower()


def match_headers(headers: list[Any]) -> dict[str, int]:
    """Column index per known key. Unknown columns are ignored; missing required ones raise."""
    wanted = {_header_text(t): key for key, texts in _HEADERS.items() for t in texts}
    found: dict[str, int] = {}
    for index, header in enumerate(headers):
        key = wanted.get(_header_text(header))
        if key is not None and key not in found:
            found[key] = index
    missing = [label for key, label in REQUIRED.items() if key not in found]
    if missing:
        raise MissingColumns(missing)
    return found


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def clean_text(value: Any) -> str | None:
    """Trimmed, inner spaces collapsed (no-break spaces too); empty → None."""
    text = _as_text(value)
    if text is None:
        return None
    text = _SPACES.sub(" ", text.replace(" ", " ")).strip()
    return text or None


_LEGACY_NUMBER = re.compile(r"T3C-?([0-9]{1,3})")


def clean_legacy_number(value: Any) -> str | None:
    """`T3C-001` … `T3C-999`, from «t3c-7», «T3C 012», Arabic digits; anything else → None."""
    text = clean_text(value)
    if text is None:
        return None
    match = _LEGACY_NUMBER.fullmatch(to_latin_digits(text).upper().replace(" ", ""))
    if match is None or int(match.group(1)) == 0:
        return None
    return f"T3C-{int(match.group(1)):03d}"


def clean_phone(value: Any) -> tuple[str | None, str | None]:
    """(§8.1 phone or None, flag or None)."""
    text = clean_text(value)
    if text is None:
        return None, "phone_missing"
    phone = normalize_phone(text)
    return phone, (None if phone else "phone_invalid")


_STAMP = re.compile(
    r"(?P<a>\d{1,4})[/-](?P<b>\d{1,2})[/-](?P<c>\d{1,4})"
    r"(?:\s+(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?(?:\s*(?P<ampm>ص|م|AM|PM))?)?",
    re.IGNORECASE,
)


def parse_timestamp(value: Any) -> datetime | None:
    """The form's «طابع زمني» as UTC. Naive values are Baghdad time (Principle X).

    Accepts an xlsx datetime, `YYYY/MM/DD HH:MM[:SS]`, `DD/MM/YYYY HH:MM[:SS]` (Sheets in Iraq),
    with Arabic digits and «ص»/«م». Anything else → None.
    """
    if isinstance(value, datetime):
        local = value if value.tzinfo else value.replace(tzinfo=BAGHDAD)
        return local.astimezone(UTC)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=BAGHDAD).astimezone(UTC)
    text = clean_text(value)
    if text is None:
        return None
    match = _STAMP.fullmatch(to_latin_digits(text))
    if match is None:
        return None
    a, b, c = match["a"], match["b"], match["c"]
    if len(a) == 4:
        year, month, day = int(a), int(b), int(c)
    elif len(c) == 4:
        day, month, year = int(a), int(b), int(c)
    else:
        return None
    hour = int(match["h"] or 0)
    minute = int(match["m"] or 0)
    second = int(match["s"] or 0)
    ampm = (match["ampm"] or "").upper()
    if ampm in ("م", "PM") and hour < 12:
        hour += 12
    elif ampm in ("ص", "AM") and hour == 12:
        hour = 0
    try:
        local = datetime(year, month, day, hour, minute, second, tzinfo=BAGHDAD)
    except ValueError:
        return None
    return local.astimezone(UTC)


def counts_in_check(status: Any) -> bool:
    """False only for «ملغي» and «مرفوض» after trimming (research R3)."""
    return (clean_text(status) or "") not in EXCLUDED_STATUSES


_DRIVE_ID = re.compile(
    r"https?://drive\.google\.com/(?:open\?(?:[^\s,]*&)?id=|uc\?(?:[^\s,]*&)?id=|file/d/)"
    r"([A-Za-z0-9_-]{10,})"
)


def drive_file_id(value: Any) -> str | None:
    """The Drive file id of the first link in the cell, or None."""
    text = _as_text(value)
    if not text:
        return None
    match = _DRIVE_ID.search(text)
    return match.group(1) if match else None


def _flag(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, **details}


def clean_row(index: int, raw: dict[str, Any]) -> dict[str, Any]:
    """One `PreviewRow` (data-model.md) without images or cross-row flags.

    `raw` maps the keys of `match_headers` to cell values; absent keys are empty cells.
    """
    names = {
        "first": clean_text(raw.get("first_name")),
        "second": clean_text(raw.get("second_name")),
        "third": clean_text(raw.get("third_name")),
    }
    family_file = clean_text(raw.get("family_number"))
    key = family_key(family_file)
    phone_file = _as_text(raw.get("phone"))
    phone, phone_flag = clean_phone(raw.get("phone"))
    legacy_number = clean_legacy_number(raw.get("legacy_number"))
    stamp = parse_timestamp(raw.get("timestamp"))
    drive_ids = {
        "front": drive_file_id(raw.get("front_image")),
        "back": drive_file_id(raw.get("back_image")),
    }

    flags: list[dict[str, Any]] = []
    if legacy_number is None:
        flags.append(_flag("legacy_number_missing"))
    if names["first"] is None:
        flags.append(_flag("name_missing"))
    if phone_flag:
        flags.append(_flag(phone_flag))
    if key is None:
        flags.append(_flag("family_missing"))
    elif len(key) != FAMILY_KEY_LENGTH:
        flags.append(_flag("family_length"))
    if phone is None and key is None:
        flags.append(_flag("no_check_keys"))
    for side in ("front", "back"):
        if drive_ids[side] is None:
            flags.append(_flag("image_missing", side=side))

    status_text = clean_text(raw.get("status"))
    return {
        "index": index,
        "legacy_number": legacy_number,
        "legacy_number_file": clean_text(raw.get("legacy_number")),
        "names": names,
        "full_name": " ".join(part for part in names.values() if part),
        "family_number_file": family_file,
        "family_key": key,
        "phone_file": phone_file,
        "phone": phone,
        "status_text": status_text,
        "counts_in_check": counts_in_check(status_text),
        "extra": {k: clean_text(raw.get(k)) for k in EXTRA_KEYS},
        "form_submitted_at": stamp.isoformat() if stamp else None,
        "drive_ids": drive_ids,
        "flags": flags,
    }


# --- flags across rows and against stored data (research R6) ---


@dataclass(frozen=True)
class Existing:
    """What is already stored. Legacy phones and family keys are those of subscribers counted in
    the check; Sijil keys map to the request numbers of live pending, approved or linked
    requests (rejected and deleted requests never count, §6.1, §7.4)."""

    legacy_numbers: frozenset[str] = frozenset()
    legacy_phones: frozenset[str] = frozenset()
    legacy_family_keys: frozenset[str] = frozenset()
    sijil_phones: Mapping[str, list[str]] = field(default_factory=dict)
    sijil_family_keys: Mapping[str, list[str]] = field(default_factory=dict)


# Only skip is possible: the row cannot be stored without these.
_SKIP_ONLY = frozenset({"legacy_number_missing", "name_missing"})


def allowed_choices(flags: list[dict[str, Any]]) -> list[str]:
    codes = {f["code"] for f in flags}
    if "already_imported" in codes:
        return []
    if codes & _SKIP_ONLY:
        return ["skip"]
    if "family_length" in codes:
        return ["import", "skip", "correct"]
    return ["import", "skip"]


def _others(groups: dict[str, list[int]], key: str | None, index: int) -> list[int]:
    if key is None:
        return []
    return [i for i in groups.get(key, []) if i != index]


def _request_order(label: str) -> int:
    return int(label.removeprefix("T3C-"))


def compute_flags(rows: list[dict[str, Any]], existing: Existing) -> list[dict[str, Any]]:
    """New rows with `flags` and `allowed`, from each row's `base_flags` and `images` outcomes,
    repeats in the file, stored legacy subscribers and Sijil requests. The input is unchanged.

    Order: the row's own flags, image failures, then family, phone, Sijil and legacy number
    conflicts. A row already imported carries only `already_imported` and is left out of the
    file repeats. Rows not counted in the check take and give no conflict flag.
    """
    out = [copy.deepcopy(row) for row in rows]
    imported = {row["index"] for row in out if row["legacy_number"] in existing.legacy_numbers}
    live = [row for row in out if row["index"] not in imported]
    counted = [row for row in live if row["counts_in_check"]]
    by_family: dict[str, list[int]] = defaultdict(list)
    by_phone: dict[str, list[int]] = defaultdict(list)
    for row in counted:
        if row["family_key"]:
            by_family[row["family_key"]].append(row["index"])
        if row["phone"]:
            by_phone[row["phone"]].append(row["index"])
    by_number: dict[str, list[int]] = defaultdict(list)
    for row in live:
        if row["legacy_number"]:
            by_number[row["legacy_number"]].append(row["index"])

    for row in out:
        if row["index"] in imported:
            row["flags"] = [_flag("already_imported")]
            row["allowed"] = []
            continue
        flags = list(row["base_flags"])
        for side in ("front", "back"):
            outcome = row.get("images", {}).get(side, {}).get("outcome")
            if outcome not in (None, "ok", "missing"):
                flags.append(_flag("image_failed", side=side, outcome=outcome))
        if row["counts_in_check"]:
            key, phone, index = row["family_key"], row["phone"], row["index"]
            if same := _others(by_family, key, index):
                flags.append(_flag("family_dup_file", rows=same))
            if key and key in existing.legacy_family_keys:
                flags.append(_flag("family_dup_legacy"))
            if same := _others(by_phone, phone, index):
                flags.append(_flag("phone_dup_file", rows=same))
            if phone and phone in existing.legacy_phones:
                flags.append(_flag("phone_dup_legacy"))
            requests = set(existing.sijil_phones.get(phone, []) if phone else [])
            requests |= set(existing.sijil_family_keys.get(key, []) if key else [])
            if requests:
                flags.append(_flag("in_sijil", requests=sorted(requests, key=_request_order)))
        if same := _others(by_number, row["legacy_number"], row["index"]):
            flags.append(_flag("legacy_number_dup_file", rows=same))
        row["flags"] = flags
        row["allowed"] = allowed_choices(flags)
    return out
