"""The «بانتظار الربط» search box (specs/013 research R7, FR-003), against a fixture. No database.

One kind per text: a request number first, then a full phone (§8.1), then a username
(`<tower code>-07XXXXXXXXX`, compared upper-cased). Anything else searches nothing.
"""

import json
from pathlib import Path

import pytest

from app.core.link_search import classify

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "link_search_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: repr(c["q"]))
def test_classify(case) -> None:
    term = classify(case["q"])
    if case["kind"] is None:
        assert term is None
    else:
        assert (term.kind, term.value) == (case["kind"], case["value"])
