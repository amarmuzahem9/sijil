"""Family number comparison key (docs/system.md §6.2, specs/008 research R3).

The family number is stored as written; this key is what duplicate checks compare: Arabic and
Persian digits → Latin, upper case, only A–Z and 0–9 kept, and every `O` read as `0` (the old data
mixes them). Unlike the 006 reading rule, the shape is not checked: legacy values have odd lengths.
"""

import re

from app.core.phone import to_latin_digits

_KEEP = re.compile(r"[^A-Z0-9]")


def family_key(text: str | None) -> str | None:
    """The comparison key, or None when nothing comparable is left."""
    if text is None:
        return None
    key = _KEEP.sub("", to_latin_digits(text).upper()).replace("O", "0")
    return key or None
