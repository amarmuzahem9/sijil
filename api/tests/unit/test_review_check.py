"""The re-check after a pin and the review warnings (specs/010 research R5). No database."""

from app.core.matches import Matches, MatchRecord, MatchRef
from app.core.review_check import review


def rec(ref: str, **flags) -> MatchRecord:
    return MatchRecord("sijil", ref, **flags)


def ref(ref_id: str) -> MatchRef:
    return MatchRef("sijil", ref_id)


def run(type_="new", matches=(), return_refs=(), basis=None, prior=()):
    return review(
        type_,
        list(return_refs),
        basis,
        Matches(list(matches)),
        set(prior),
    )


def test_no_matches_gives_nothing() -> None:
    result = run()
    assert (result.open_rows, result.new_type, result.warnings) == ([], "new", [])


def test_new_with_a_family_record_becomes_additional() -> None:
    result = run("new", [rec("7", family=True)])
    assert result.open_rows == [("family_exists", ref("7"))]
    assert result.new_type == "additional"
    assert result.warnings == []


def test_additional_without_its_family_record_stays_additional() -> None:
    result = run("additional", [])
    assert (result.open_rows, result.new_type) == ([], "additional")


def test_same_person_on_new_warns() -> None:
    result = run("new", [rec("7", national_id=True, family=True)])
    assert result.warnings == ["same_person"]
    # Same person is not a pending reason: it has no reason row.
    assert result.open_rows == []
    assert result.new_type == "new"


def test_same_person_on_additional_warns() -> None:
    result = run("additional", [rec("7", national_id=True, family=True)])
    assert result.warnings == ["same_person"]


def test_new_conflict_after_the_pin_warns() -> None:
    result = run("new", [rec("8", national_id=True)])
    assert result.open_rows == [("numbers_conflict", ref("8"))]
    assert result.warnings == ["id_conflict"]


def test_conflict_already_on_the_request_does_not_warn() -> None:
    result = run("new", [rec("8", national_id=True)], prior=[ref("8")])
    assert result.open_rows == [("numbers_conflict", ref("8"))]
    assert result.warnings == []


def test_identity_return_whose_target_no_longer_matches_warns() -> None:
    # Record 7 was the same person; after the pin only its family number matches.
    result = run("return", [rec("7", family=True)], return_refs=[ref("7")], basis="identity")
    assert result.warnings == ["return_target_lost"]
    # A target record is never turned into a family row.
    assert result.open_rows == []
    assert result.new_type == "return"


def test_identity_return_still_matching_does_not_warn() -> None:
    result = run(
        "return",
        [rec("7", national_id=True, family=True, phone=True)],
        return_refs=[ref("7")],
        basis="identity",
    )
    assert result.warnings == []


def test_phone_return_never_loses_its_target() -> None:
    result = run("return", [rec("7", phone=True)], return_refs=[ref("7")], basis="phone")
    assert result.warnings == []


def test_return_with_a_family_record_outside_the_target() -> None:
    result = run(
        "return",
        [rec("7", national_id=True, family=True), rec("9", family=True)],
        return_refs=[ref("7")],
        basis="identity",
    )
    assert result.open_rows == [("family_exists", ref("9"))]
    assert result.new_type == "return"
    assert result.warnings == []


def test_same_person_on_a_return_is_its_target_not_a_warning() -> None:
    result = run(
        "return",
        [rec("7", national_id=True, family=True)],
        return_refs=[ref("7")],
        basis="identity",
    )
    assert "same_person" not in result.warnings


def test_warnings_keep_a_fixed_order() -> None:
    result = run(
        "new",
        [rec("8", national_id=True), rec("7", national_id=True, family=True)],
    )
    assert result.warnings == ["same_person", "id_conflict"]
