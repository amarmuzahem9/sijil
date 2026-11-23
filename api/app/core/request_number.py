"""The request number as an admin types it (specs/011 research R6).

Used by the delete confirmation and by «فتح طلب برقمه». Accepts «T3C-1005», «#T3C-1005», «1005»
and the same in Arabic-Indic (٠-٩) or Eastern Arabic (۰-۹) digits. Mirrored in
web/src/lib/requestNumber.ts; both are tested against tests/fixtures/request_number_cases.json.
"""

import re

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)
_PATTERN = re.compile(r"#?\s*(?:T3C-)?\s*([0-9]{1,9})", re.IGNORECASE)


def parse(text: str) -> int | None:
    """The number, or None when the text is not a request number."""
    match = _PATTERN.fullmatch(text.translate(_DIGITS).strip())
    if match is None:
        return None
    number = int(match.group(1))
    return number if number > 0 else None
