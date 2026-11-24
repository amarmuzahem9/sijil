"""The marketer's search box (specs/012 research R8, FR-013), against a fixture. No database.

One kind per text: a request number first, then a full phone (§8.1), then part of an Arabic name
(diacritics and tatweel removed, spaces collapsed, at least 2 letters). Anything else searches
nothing, so `%`, `_` and Latin text never reach a LIKE pattern.
"""

import json
from pathlib import Path

import pytest

from app.core.request_search import classify

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "request_search_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: repr(c["q"]))
def test_classify(case) -> None:
    term = classify(case["q"])
    if case["kind"] is None:
        assert term is None
    else:
        assert (term.kind, term.value) == (case["kind"], case["value"])
