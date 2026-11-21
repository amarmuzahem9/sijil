import json
from pathlib import Path

import pytest

from app.core.phone import normalize_phone

CASES = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "phone_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[c["note"] for c in CASES])
def test_normalize_phone(case: dict) -> None:
    assert normalize_phone(case["input"]) == case["expected"]


def test_none_is_invalid() -> None:
    assert normalize_phone(None) is None


def test_fixture_covers_required_cases() -> None:
    notes = " ".join(c["note"] for c in CASES)
    for required in ("U+202A", "U+200F", "spaces", "+964", "00964", "Arabic-Indic", "Persian"):
        assert required in notes
