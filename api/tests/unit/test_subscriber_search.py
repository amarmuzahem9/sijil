"""What the «المشتركون» search box text means (docs/system.md v1.24 §10 item 4; specs/018 research
R2, analysis A1), from the shared fixture."""

import json
from pathlib import Path

import pytest
from app.core.subscriber_search import KINDS, classify

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "subscriber_search_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: repr(c["text"]))
def test_classify(case) -> None:
    term = classify(case["text"])
    if case["kind"] is None:
        assert term is None
    else:
        assert term is not None
        assert (term.kind, term.value) == (case["kind"], case["value"])


def test_identity_kinds_need_review() -> None:
    assert {k for k in KINDS if classify_kind_requires_review(k)} == set(FIXTURE["requires_review"])


def classify_kind_requires_review(kind: str) -> bool:
    from app.core.subscriber_search import Term

    return Term(kind, "x").requires_review


def test_none_input() -> None:
    assert classify(None) is None
