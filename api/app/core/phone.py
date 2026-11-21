"""Phone normalization — docs/system.md §8.1. The server-side result is authoritative."""

import re

# Arabic-Indic (U+0660–0669) and Extended Arabic-Indic / Persian (U+06F0–06F9) → ASCII.
_DIGITS = {chr(0x0660 + i): str(i) for i in range(10)} | {
    chr(0x06F0 + i): str(i) for i in range(10)
}
_TRANSLATE = str.maketrans(_DIGITS)
_ASCII_DIGITS = frozenset("0123456789")
_VALID = re.compile(r"07\d{9}")


def normalize_phone(raw: str | None) -> str | None:
    """Return the canonical `07XXXXXXXXX` form, or None if the input is not a valid number.

    1. Convert Arabic/Persian digits to Latin.
    2. Drop everything that is not a digit (spaces, dashes, `+`, hidden direction marks…).
    3. `00964…` / `964…` → `0…`.
    4. 10 digits starting with 7 → prefix 0.
    5. Only `^07\\d{9}$` is valid.
    """
    if raw is None:
        return None
    digits = "".join(c for c in raw.translate(_TRANSLATE) if c in _ASCII_DIGITS)
    if digits.startswith("00964"):
        digits = "0" + digits[5:]
    elif digits.startswith("964"):
        digits = "0" + digits[3:]
    if len(digits) == 10 and digits.startswith("7"):
        digits = "0" + digits
    return digits if _VALID.fullmatch(digits) else None
