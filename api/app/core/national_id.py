"""National ID normalization (docs/system.md §2, specs/005 research.md R9).

The unified national card number is 12 digits. Drafts keep the text as typed; this canonical form
is used for validation and, from feature 008, for duplicate comparison (Principle I).
"""

import re

from app.core.phone import to_latin_digits

# Spaces of any kind and the invisible direction marks phones paste around numbers.
_STRIP = re.compile(r"[\s\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\ufeff]")
_VALID = re.compile(r"\d{12}")


def normalize_national_id(raw: str | None) -> str | None:
    """Return the 12 Latin digits, or None if the input is not a valid national ID.

    Arabic-Indic / Persian digits are converted; spaces and direction marks are removed. Any
    other character (letters, dashes, dots) makes the value invalid rather than being dropped,
    so a mistyped ID is reported instead of silently "fixed".
    """
    if raw is None:
        return None
    cleaned = _STRIP.sub("", to_latin_digits(raw))
    return cleaned if _VALID.fullmatch(cleaned) and cleaned.isascii() else None
