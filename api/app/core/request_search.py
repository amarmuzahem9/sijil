"""What the marketer's search box text means (specs/012 research R8, FR-013).

One kind per text, in this order:
1. a request number («1004», «T3C-1004», «#t3c-١٠٠٤»), parsed like «فتح طلب برقمه» (011);
2. a full phone in any form, normalised per docs/system.md §8.1;
3. part of an Arabic name: diacritics, tatweel and direction marks removed, spaces collapsed, at
   least 2 letters, Arabic letters and spaces only.
Anything else is not a search, so `%`, `_` and Latin text never reach a LIKE pattern.
"""

from dataclasses import dataclass
from typing import Literal

from app.core import request_number
from app.core.arabic_name import InvalidArabicName, clean_arabic_name
from app.core.phone import normalize_phone

MIN_LENGTH = 2


@dataclass(frozen=True)
class SearchTerm:
    kind: Literal["number", "phone", "name"]
    value: int | str


def classify(text: str) -> SearchTerm | None:
    number = request_number.parse(text)
    if number is not None:
        return SearchTerm("number", number)
    phone = normalize_phone(text)
    if phone is not None:
        return SearchTerm("phone", phone)
    try:
        name = clean_arabic_name(text)
    except InvalidArabicName:
        return None
    if name is None or len(name.replace(" ", "")) < MIN_LENGTH:
        return None
    return SearchTerm("name", name)
