"""Name fields of the ministry form (docs/system.md §5.1 v1.5, specs/005 research.md R12).

Each name: Arabic letters and single spaces only. Diacritics, tatweel and invisible direction
marks are removed, spaces are trimmed and collapsed. Digits of any script, Latin letters and
symbols are refused. Client mirror: web/src/lib/arabicName.ts (same shared fixture).

The character classes are built from code points so that no invisible or combining character
is written literally in this file.
"""

import re
import unicodedata


def _ranges(*pairs: tuple[int, int]) -> str:
    return "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in pairs)


# Arabic letters, including the Persian/Iraqi additions (پ چ ژ ڤ ک گ ی) in U+0671–U+06D3.
_LETTERS = _ranges((0x0621, 0x063A), (0x0641, 0x064A), (0x0671, 0x06D3))
# Diacritics (harakat, shadda, sukun, superscript alef), tatweel and direction marks.
_REMOVED = (
    _ranges((0x064B, 0x065F), (0x200E, 0x200F), (0x202A, 0x202E), (0x2066, 0x2069))
    + chr(0x0670)
    + chr(0x0640)
    + chr(0x061C)
    + chr(0xFEFF)
)
_REMOVE = re.compile(f"[{_REMOVED}]")
_SPACES = re.compile(r"\s+")
_VALID = re.compile(f"[{_LETTERS}]+(?: [{_LETTERS}]+)*")


class InvalidArabicName(ValueError):
    """The name contains a digit, a non-Arabic letter or a symbol."""


def clean_arabic_name(raw: str | None) -> str | None:
    """Return the cleaned name, None when empty, or raise InvalidArabicName."""
    if raw is None:
        return None
    text = _REMOVE.sub("", unicodedata.normalize("NFC", raw))
    text = _SPACES.sub(" ", text).strip()
    if not text:
        return None
    if not _VALID.fullmatch(text):
        raise InvalidArabicName(text)
    return text


_PLACE_SEPARATORS = re.compile(r"\s*([-/])\s*")


def clean_place_text(raw: str | None) -> str | None:
    """A place name such as «تكريت-صلاح الدين» (specs/006 FR-028): Arabic words separated by
    spaces, «-» or «/». Returns the cleaned text, None when empty, or raises InvalidArabicName."""
    if raw is None or not raw.strip():
        return None
    parts = _PLACE_SEPARATORS.split(raw.strip())
    out: list[str] = []
    for part in parts:
        if part in ("-", "/"):
            if not out or out[-1] in ("-", "/"):
                raise InvalidArabicName(raw)
            out.append(part)
            continue
        cleaned = clean_arabic_name(part)
        if cleaned is None:
            raise InvalidArabicName(raw)
        out.append(cleaned)
    if out[-1] in ("-", "/"):
        raise InvalidArabicName(raw)
    return "".join(out)


def join_full_name(parts: list[str | None]) -> str | None:
    """`full_name`: the given parts joined by one space, empty parts skipped; None if all empty."""
    words = [p for p in parts if p]
    return " ".join(words) or None
