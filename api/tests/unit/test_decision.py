"""The §6.1 decision table as a pure function (specs/008 research R2, specs/009 research R4)."""

import pytest

from app.core.decision import Decision, decide
from app.core.matches import Matches, MatchRecord, MatchRef

PHONE = MatchRecord("sijil", "1", phone=True)
SAME = MatchRecord("sijil", "2", national_id=True, family=True)
CONFLICT = MatchRecord("sijil", "3", national_id=True)
FAMILY = MatchRecord("sijil", "7", family=True)
FAM = [FAMILY.ref]


def _m(phone=False, same=False, conflict=False, family=False) -> Matches:
    records = []
    if phone:
        records.append(PHONE)
    if same:
        records.append(SAME)
    if conflict:
        records.append(CONFLICT)
    if family:
        records.append(FAMILY)
    return Matches(records)


# --- 008 rows, with "national ID exists" now meaning the same person (v1.10 row 2) ---


def test_row5_clean_is_approved() -> None:
    d = decide(_m(), edited_fields=[], additional_confirmed=False)
    assert d == Decision(refusal=None, type="new", status="approved", reasons=[], result="approved")


def test_row1_phone_used_refuses() -> None:
    assert decide(_m(phone=True), [], False).refusal == "phone_used"


def test_row2_same_person_refuses_as_new() -> None:
    assert decide(_m(same=True), [], False).refusal == "national_id_exists"


@pytest.mark.parametrize(
    ("matches", "edited"),
    [
        (_m(phone=True, same=True), []),
        (_m(phone=True, family=True), []),
        (_m(phone=True, conflict=True), []),
        (_m(phone=True), ["family_number"]),
    ],
)
def test_row1_beats_everything(matches, edited) -> None:
    assert decide(matches, edited, True).refusal == "phone_used"


@pytest.mark.parametrize("edited", [[], ["national_id"]])
def test_row2_beats_rows_3_and_4(edited) -> None:
    assert decide(_m(same=True, family=True), edited, True).refusal == "national_id_exists"


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


# --- v1.10 row 2b: national ID matches, family number differs (owner's Q2) ---


def test_conflict_goes_to_review_as_new() -> None:
    d = decide(_m(conflict=True), [], False)
    assert (d.refusal, d.type, d.status, d.result) == (
        None,
        "new",
        "pending_review",
        "pending_approval",
    )
    assert [(r.reason, r.matches) for r in d.reasons] == [("numbers_conflict", [CONFLICT.ref])]


def test_conflict_with_confirmed_family_is_additional_with_both_reasons() -> None:
    d = decide(_m(conflict=True, family=True), [], True)
    assert (d.type, d.result) == ("additional", "pending_family")
    assert [r.reason for r in d.reasons] == ["numbers_conflict", "family_exists"]


def test_conflict_with_unconfirmed_family_is_incomplete() -> None:
    assert decide(_m(conflict=True, family=True), [], False).refusal == "draft_incomplete"


def test_conflict_and_edited_record_both() -> None:
    d = decide(_m(conflict=True), ["national_id"], False)
    assert [r.reason for r in d.reasons] == ["numbers_conflict", "numbers_edited"]


# --- v1.10 return to service (research R4) ---


def test_return_by_identity_is_pending_return() -> None:
    d = decide(_m(same=True), [], False, return_valid=True)
    assert (d.refusal, d.type, d.status, d.result) == (
        None,
        "return",
        "pending_review",
        "pending_approval",
    )
    assert [(r.reason, r.matches, r.basis) for r in d.reasons] == [
        ("return", [SAME.ref], "identity")
    ]


def test_return_with_edited_numbers_records_both() -> None:
    d = decide(_m(same=True), ["family_number"], False, return_valid=True)
    assert [r.reason for r in d.reasons] == ["return", "numbers_edited"]


def test_return_by_identity_refuses_a_phone_outside_the_target() -> None:
    assert decide(_m(phone=True, same=True), [], False, return_valid=True).refusal == "phone_used"


def test_return_allows_the_targets_own_phone() -> None:
    own = MatchRecord("sijil", "2", phone=True, national_id=True, family=True)
    d = decide(Matches([own]), [], False, return_valid=True)
    assert (d.refusal, d.type) == (None, "return")


def test_return_by_phone() -> None:
    d = decide(_m(phone=True), [], False, return_valid=True)
    assert (d.refusal, d.type) == (None, "return")
    assert [(r.reason, r.matches, r.basis) for r in d.reasons] == [("return", [PHONE.ref], "phone")]


@pytest.mark.parametrize(
    "target",
    [
        MatchRecord("sijil", "2", national_id=True, family=True, pending=True),
        MatchRecord("sijil", "1", phone=True, pending=True),
    ],
)
def test_return_with_a_pending_record_in_the_target_refuses(target) -> None:
    assert decide(Matches([target]), [], False, return_valid=True).refusal == "return_pending"


def test_return_records_family_outside_the_target_without_confirmation() -> None:
    d = decide(_m(same=True, family=True), [], False, return_valid=True)
    assert d.refusal is None
    assert [(r.reason, r.matches) for r in d.reasons] == [
        ("return", [SAME.ref]),
        ("family_exists", FAM),
    ]
    assert d.type == "return"


def test_return_by_phone_records_a_conflict_outside_the_target() -> None:
    d = decide(_m(phone=True, conflict=True), [], False, return_valid=True)
    assert [r.reason for r in d.reasons] == ["return", "numbers_conflict"]


def test_return_valid_without_target_falls_back_to_the_normal_rules() -> None:
    # A stale choice: nothing to return to, so the draft is judged as new.
    d = decide(_m(), [], False, return_valid=True)
    assert (d.type, d.status) == ("new", "approved")


def test_matches_of_reasons_are_refs() -> None:
    d = decide(_m(conflict=True), [], False)
    assert all(isinstance(m, MatchRef) for r in d.reasons for m in r.matches)
