"""The §6.1 decision table as a pure function (specs/008 research R2)."""

import pytest

from app.core.decision import Decision, decide
from app.services.match_service import Matches, MatchRef

FAM = [MatchRef("sijil", "7")]


def _m(phone=False, nid=False, family=False) -> Matches:
    return Matches(
        phone=[MatchRef("sijil", "1")] if phone else [],
        national_id=[MatchRef("sijil", "2")] if nid else [],
        family=list(FAM) if family else [],
    )


def test_row5_clean_is_approved() -> None:
    d = decide(_m(), edited_fields=[], additional_confirmed=False)
    assert d == Decision(refusal=None, type="new", status="approved", reasons=[], result="approved")


def test_row1_phone_used_refuses() -> None:
    assert decide(_m(phone=True), [], False).refusal == "phone_used"


def test_row2_national_id_refuses() -> None:
    assert decide(_m(nid=True), [], False).refusal == "national_id_exists"


@pytest.mark.parametrize(
    ("matches", "edited"),
    [
        (_m(phone=True, nid=True), []),
        (_m(phone=True, family=True), []),
        (_m(phone=True), ["family_number"]),
    ],
)
def test_row1_beats_everything(matches, edited) -> None:
    assert decide(matches, edited, True).refusal == "phone_used"


@pytest.mark.parametrize("edited", [[], ["national_id"]])
def test_row2_beats_rows_3_and_4(edited) -> None:
    assert decide(_m(nid=True, family=True), edited, True).refusal == "national_id_exists"


def test_row3_family_is_additional_pending() -> None:
    d = decide(_m(family=True), [], additional_confirmed=True)
    assert (d.refusal, d.type, d.status, d.result) == (
        None,
        "additional",
        "pending_review",
        "pending_family",
    )
    assert [r.reason for r in d.reasons] == ["family_exists"]
    assert d.reasons[0].matches == FAM


def test_row3_unconfirmed_is_refused_as_incomplete() -> None:
    # The page blocks it as a missing item; decide() refuses defensively.
    assert decide(_m(family=True), [], additional_confirmed=False).refusal == "draft_incomplete"


def test_row4_edited_is_pending_review() -> None:
    d = decide(_m(), ["family_number"], False)
    assert (d.type, d.status, d.result) == ("new", "pending_review", "pending_review")
    assert [(r.reason, r.fields) for r in d.reasons] == [("numbers_edited", ["family_number"])]


def test_rows_3_and_4_together_record_both_reasons_in_order() -> None:
    d = decide(_m(family=True), ["national_id", "family_number"], True)
    assert (d.type, d.status, d.result) == ("additional", "pending_review", "pending_family")
    assert [r.reason for r in d.reasons] == ["family_exists", "numbers_edited"]
