"""Arabic name folding for the subscriber search (docs/system.md v1.24 §10 item 4; specs/018
research R3): different spellings of the same name fold to the same text."""

import pytest

from app.core.arabic_name import fold_arabic


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("أحمد", "احمد"),
        ("إبراهيم", "ابراهيم"),
        ("آمنة", "امنه"),
        ("ٱلعلي", "العلي"),
        ("فاطمة", "فاطمه"),
        ("مصطفى", "مصطفي"),
        ("مُحَمَّد", "محمد"),  # diacritics
        ("علــي", "علي"),  # tatweel
        ("‏علي‎", "علي"),  # direction marks
        ("  علي   حسين  ", "علي حسين"),
    ],
)
def test_fold(raw: str, folded: str) -> None:
    assert fold_arabic(raw) == folded


def test_spellings_meet() -> None:
    assert fold_arabic("أحمد علي") == fold_arabic("احمد علي")
    assert fold_arabic("زينة") == fold_arabic("زينه")
    assert fold_arabic("هدى") == fold_arabic("هدي")


@pytest.mark.parametrize("raw", [None, "", "   ", "‏"])
def test_empty(raw) -> None:
    assert fold_arabic(raw) is None
