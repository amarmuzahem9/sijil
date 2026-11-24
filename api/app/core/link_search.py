"""What the «بانتظار الربط» search box text means (specs/013 research R7, FR-003).

One kind per text, in this order:
1. a request number («1004», «T3C-1004», «#t3c-١٠٠٤»), parsed like «فتح طلب برقمه» (011);
2. a full phone in any form, normalised per docs/system.md §8.1;
3. a username `<tower code>-07XXXXXXXXX`, upper-cased (SAS usernames are compared that way).
Anything else is not a search: the admin finds a subscriber in SAS by these three only.
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.core import request_number
from app.core.phone import normalize_phone, to_latin_digits

MIN_LENGTH = 2

_USERNAME = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*-07[0-9]{9}")


@dataclass(frozen=True)
class LinkSearchTerm:
    kind: Literal["number", "phone", "username"]
    value: int | str


def classify(text: str) -> LinkSearchTerm | None:
    number = request_number.parse(text)
    if number is not None:
        return LinkSearchTerm("number", number)
    phone = normalize_phone(text)
    if phone is not None:
        return LinkSearchTerm("phone", phone)
    username = to_latin_digits(text).strip().upper()
    if _USERNAME.fullmatch(username):
        return LinkSearchTerm("username", username)
    return None
