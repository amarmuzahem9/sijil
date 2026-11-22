import json
from pathlib import Path

import pytest

from app.core.national_id import normalize_national_id

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "draft_validation_cases.json").read_text("utf-8")
)
CASES = FIXTURE["national_id"]


@pytest.mark.parametrize("case", CASES, ids=[c["note"] for c in CASES])
def test_normalize_national_id(case: dict) -> None:
    assert normalize_national_id(case["input"]) == case["expected"]


def test_none_is_invalid() -> None:
    assert normalize_national_id(None) is None


def test_other_unicode_digits_are_refused() -> None:
    # Bengali digits match \d in Python; only Arabic-Indic/Persian are converted (§8.1 style).
    assert normalize_national_id("১৯৯০১২৩৪৫৬৭৮") is None


def test_fixture_covers_required_cases() -> None:
    notes = " ".join(c["note"] for c in CASES)
    for required in ("11 digits", "12 digits", "13 digits", "Arabic-Indic", "spaces", "letters"):
        assert required in notes
