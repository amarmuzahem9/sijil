"""§6.2 family comparison key (specs/008 research R3)."""

import json
from pathlib import Path

import pytest

from app.core.family_key import family_key

CASES = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "family_key_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=[c["note"] for c in CASES])
def test_family_key(case: dict) -> None:
    assert family_key(case["input"]) == case["expected"]


def test_none() -> None:
    assert family_key(None) is None


def test_written_forms_share_a_key() -> None:
    forms = ["1234A5678901234567", "1234 a 5678901234567", "1234A56789O1234567".replace("O", "0")]
    assert len({family_key(f) for f in forms}) == 1


def test_o_and_zero_compare_equal_everywhere() -> None:
    assert family_key("1234O5678901234567") == family_key("123405678901234567")
