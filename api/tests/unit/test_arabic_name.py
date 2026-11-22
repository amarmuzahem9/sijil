import json
from pathlib import Path

import pytest

from app.core.arabic_name import InvalidArabicName, clean_arabic_name, join_full_name

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "draft_validation_cases.json").read_text("utf-8")
)
CASES = FIXTURE["names"]


@pytest.mark.parametrize("case", CASES, ids=[c["note"] for c in CASES])
def test_clean_arabic_name(case: dict) -> None:
    if case["valid"]:
        assert clean_arabic_name(case["input"]) == case["expected"]
    else:
        with pytest.raises(InvalidArabicName):
            clean_arabic_name(case["input"])


def test_none_stays_none() -> None:
    assert clean_arabic_name(None) is None


def test_join_full_name_skips_empty_parts() -> None:
    assert join_full_name(["علي", "حسن", None, "", "الوهمي"]) == "علي حسن الوهمي"
    assert join_full_name([None, "", None]) is None
