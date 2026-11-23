"""The typed request number (specs/011 research R6), against the fixture shared with the web."""

import json
from pathlib import Path

import pytest

from app.core.request_number import parse

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "request_number_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: repr(c["text"]))
def test_parse(case) -> None:
    assert parse(case["text"]) == case["number"]
