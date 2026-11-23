"""Card reading constants and pure helpers (specs/006 data-model.md › Constants, research R6, R7).

No card content is ever logged from here.
"""

import difflib
import re
from datetime import date, timedelta
from typing import Any

from app.core.national_id import normalize_national_id
from app.core.phone import to_latin_digits

# --- Detection classes of the reader (contracts/ocr-service.md) ---------------------------------
FRONT_CLASS = "iraq id card"
BACK_CLASS = "back"
OTHER_DOCUMENT_CLASSES = ("addres", "car", "drive")
SIDE_CLASS = {"front": FRONT_CLASS, "back": BACK_CLASS}

# --- Thresholds (data-model.md › Constants) ------------------------------------------------------
SECOND_PASS_MIN = 0.50  # upstream threshold for a card candidate
SECOND_DOC_HIGH = 0.90  # R6.4: above step 0's phantom front (0.876)
DUPLICATE_IOU = 0.5  # R6.3
OTHER_DOC_MIN = 0.50  # R6.1
READING_LIMIT_S = 60  # FR-014
READER_HTTP_TIMEOUT_S = 45  # R5

# Front labels of the reader that count as readable card fields (R6.4).
FRONT_LABELS = ("name", "dad", "gf", "last", "mom", "gm", "gn", "id", "id2")

FAMILY_NUMBER_RE = re.compile(r"\d{4}[A-Z][0-9A-Z]{13}")

# --- Back fields (owner change; research R13, system.md v1.8) -----------------------------------
CARD_VALIDITY_YEARS = 10  # expiry = issue + 10 years - 1 day (all sample cards)
KNOWN_AUTHORITIES = ("مديرية الجنسية والمعلومات المدنية",)
AUTHORITY_MIN_SIMILARITY = 0.70
BIRTH_PLACE_MAX = 100
AUTHORITY_MAX = 100
PRINTED_BIRTH_MIN_AGREEMENT = 2


def mrz_check_digit(data: str) -> str:
    """ICAO 9303 check digit: weights 7, 3, 1; '<' = 0; A = 10 … Z = 35."""
    total = 0
    for i, char in enumerate(data):
        if char.isdigit():
            value = int(char)
        elif "A" <= char <= "Z":
            value = ord(char) - ord("A") + 10
        else:
            value = 0
        total += value * (7, 3, 1)[i % 3]
    return str(total % 10)


def mrz_verified(mrz: dict[str, Any] | None) -> bool:
    """A TD1 zone whose four check digits are all correct (R7). A null composite is not."""
    if not mrz or mrz.get("mrz_type") != "TD1":
        return False
    checks = ("valid_number", "valid_date_of_birth", "valid_expiration_date", "valid_composite")
    return all(mrz.get(key) is True for key in checks)


def mrz_national_id(mrz: dict[str, Any] | None) -> str | None:
    """The national ID carried in a verified MRZ (`optional1`), as 12 digits, else None."""
    if not mrz_verified(mrz):
        return None
    return normalize_national_id((mrz.get("optional1") or "").replace("<", ""))


def normalize_family_number(text: str | None) -> str | None:
    """R6.6: upper-case, no spaces; `O` → `0` except at the series letter (position 4); then the
    shape must be 4 digits, one Latin letter, 13 Latin letters or digits. Else None."""
    if not text:
        return None
    value = re.sub(r"\s+", "", text).upper()
    value = "".join("0" if c == "O" and i != 4 else c for i, c in enumerate(value))
    return value if value.isascii() and FAMILY_NUMBER_RE.fullmatch(value) else None


_DATE_TEXT = re.compile(r"(\d{4})\D{0,2}(\d{1,2})\D{0,2}(\d{1,2})")


def parse_printed_date(text: str | None) -> date | None:
    """A printed date such as `2023/06/15` (Arabic-Indic digits accepted), else None."""
    if not text:
        return None
    cleaned = to_latin_digits(text).replace(" ", "")
    match = _DATE_TEXT.search(cleaned)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def mrz_date(yymmdd: str | None, century: str) -> date | None:
    """`YYMMDD` from the MRZ with the given century (`"19"` or `"20"`), else None."""
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    try:
        return date(int(century + yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6]))
    except ValueError:
        return None


def issue_for_expiry(expiry: date) -> date | None:
    """The issue date implied by an expiry date: expiry - 10 years + 1 day (R13)."""
    try:
        return expiry.replace(year=expiry.year - CARD_VALIDITY_YEARS) + timedelta(days=1)
    except ValueError:  # 29 February
        return date(expiry.year - CARD_VALIDITY_YEARS, 3, 1)


def birth_century(national_id: str | None, yy: str, today: date) -> str:
    """Century of a two-digit birth year: from the national ID's first two digits, else the
    usual rule (a year after this year's two digits is 19xx)."""
    if national_id and len(national_id) == 12 and national_id[:2] in ("19", "20"):
        return national_id[:2]
    return "19" if int(yy) > today.year % 100 else "20"


def snap_authority(text: str | None) -> str | None:
    """The known issuing authority the text is similar enough to (≥ 0.70), else None."""
    if not text or not text.strip():
        return None
    best = max(
        KNOWN_AUTHORITIES,
        key=lambda known: difflib.SequenceMatcher(None, text.strip(), known).ratio(),
    )
    ratio = difflib.SequenceMatcher(None, text.strip(), best).ratio()
    return best if ratio >= AUTHORITY_MIN_SIMILARITY else None


# Governorates and their main cities: a known place glued to the word before it gets the «-»
# the recogniser dropped (owner decision, option 1; research R13).
KNOWN_PLACES = (
    "صلاح الدين",
    "بغداد",
    "البصرة",
    "نينوى",
    "اربيل",
    "السليمانية",
    "دهوك",
    "كركوك",
    "الانبار",
    "ديالى",
    "بابل",
    "كربلاء",
    "النجف",
    "واسط",
    "القادسية",
    "ذي قار",
    "ميسان",
    "المثنى",
    "تكريت",
    "الموصل",
    "الرمادي",
    "الفلوجة",
    "بعقوبة",
    "الحلة",
    "الكوت",
    "الديوانية",
    "الناصرية",
    "العمارة",
    "السماوة",
    "سامراء",
    "بيجي",
)
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A]")


def fix_place_separators(text: str | None) -> str | None:
    """Put back the separators the recogniser loses in a place of birth (FR-028, option 1):
    a lone «ا» between two words was a «/», and a known place glued to the previous letter gets
    a «-». A dropped letter cannot be fixed; the marketer checks the «من البطاقة» value."""
    if not text:
        return text
    words = text.split()
    for i in range(1, len(words) - 1):
        if words[i] == "ا":
            words[i] = "/"
    fixed = " ".join(words)
    for place in sorted(KNOWN_PLACES, key=len, reverse=True):
        start = 0
        while (index := fixed.find(place, start)) != -1:
            end = index + len(place)
            glued = index > 0 and _ARABIC_LETTER.match(fixed[index - 1])
            whole = end == len(fixed) or not _ARABIC_LETTER.match(fixed[end])
            if glued and whole:
                fixed = fixed[:index] + "-" + fixed[index:]
                end += 1
            start = end
    return fixed


PLACE_MIN_LETTERS = 6


def _fold(text: str) -> str:
    """Spelling-insensitive form for matching place names: أ إ آ → ا, ى → ي, ة → ه."""
    return (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ة", "ه")
    )


def looks_like_place(text: str | None) -> bool:
    """A place of birth worth filling (owner request after the staging test): at least six letters
    and at least one known governorate or main city in it. A short or unknown reading (e.g. a
    few stray letters) is left empty for the marketer."""
    if not text:
        return False
    letters = sum(1 for c in text if _ARABIC_LETTER.match(c))
    if letters < PLACE_MIN_LETTERS:
        return False
    folded = _fold(text)
    return any(_fold(place) in folded for place in KNOWN_PLACES)
