"""What the «المشتركون» search box text means (docs/system.md v1.24 §10 item 4; specs/018 research
R2). Pure; tested against tests/fixtures/subscriber_search_cases.json.

One kind per text, in this order:
1. a legacy number: «T3C-» and exactly 3 digits (checked first: request numbers start at 1001, and
   `request_number.parse` would read «T3C-001» as request 1 — analysis A1);
2. a request number («1004», «T3C-1004», «#t3c-١٠٠٤»);
3. a national ID: 12 digits, spaces and Arabic digits allowed;
4. a full phone (§8.1), from digits, spaces, «+», «-» and brackets only;
5. a family number: its comparison key (§6.2) is 10–24 characters starting with 4 digits, and the
   text has a Latin letter (legacy values have odd lengths, §12.1);
6. a username: «PREFIX-07XXXXXXXXX» (Sijil or SAS), upper-cased;
7. an Arabic name of at least 3 letters, folded.
Anything else is not a search, so `%`, `_` and Latin text never reach a LIKE pattern.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.core import request_number
from app.core.arabic_name import InvalidArabicName, clean_arabic_name, fold_arabic
from app.core.family_key import family_key
from app.core.national_id import normalize_national_id
from app.core.phone import normalize_phone, to_latin_digits
from app.core.sas_row import split_username, username_key

Kind = Literal["number", "legacy_number", "national_id", "phone", "family", "username", "name"]
KINDS: tuple[Kind, ...] = (
    "number",
    "legacy_number",
    "national_id",
    "phone",
    "family",
    "username",
    "name",
)
# Searching by these reveals whether a person exists: main admin and `review` only (owner Q2).
IDENTITY_KINDS = frozenset({"national_id", "family"})
MIN_NAME_LETTERS = 3

_LEGACY = re.compile(r"#?\s*T3C-([0-9]{3})", re.IGNORECASE)
_PHONE_TEXT = re.compile(r"[0-9\s+\-()‎‏‪-‮]+")
_FAMILY_LETTER = re.compile(r"[A-Za-z]")
_USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*-[0-9+]+")


@dataclass(frozen=True)
class Term:
    kind: Kind
    value: int | str

    @property
    def requires_review(self) -> bool:
        return self.kind in IDENTITY_KINDS


def classify(text: str | None) -> Term | None:
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None
    latin = to_latin_digits(raw)

    legacy = _LEGACY.fullmatch(latin)
    if legacy:
        return Term("legacy_number", f"T3C-{legacy.group(1)}")
    number = request_number.parse(raw)
    if number is not None:
        return Term("number", number)
    national_id = normalize_national_id(raw)
    if national_id is not None:
        return Term("national_id", national_id)
    if _PHONE_TEXT.fullmatch(latin):
        phone = normalize_phone(raw)
        if phone is not None:
            return Term("phone", phone)
    if "-" not in latin and _FAMILY_LETTER.search(latin):
        key = family_key(raw)
        if key is not None and 10 <= len(key) <= 24 and key.isascii() and key[:4].isdigit():
            return Term("family", key)
    if _USERNAME.fullmatch(latin):
        prefix, phone = split_username(latin)
        if prefix is not None and phone is not None:
            return Term("username", username_key(latin))
    try:
        name = clean_arabic_name(raw)
    except InvalidArabicName:
        return None
    if name is None or len(name.replace(" ", "")) < MIN_NAME_LETTERS:
        return None
    return Term("name", fold_arabic(name))
