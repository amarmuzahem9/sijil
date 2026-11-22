"""Card reading constants and pure helpers (specs/006 data-model.md › Constants, research R6, R7).

No card content is ever logged from here.
"""

import re
from typing import Any

from app.core.national_id import normalize_national_id

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
