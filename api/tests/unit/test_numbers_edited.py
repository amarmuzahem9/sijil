"""Row 4 «تعديل الأرقام», decided by value (specs/008 research R4, FR-005a)."""

from types import SimpleNamespace

from app.services.numbers_edited import edited_fields

NID = "199012345678"
FAM = "1234A5678901234567"


def _draft(national_id=NID, family=FAM, card_fields=None, check=None) -> SimpleNamespace:
    if card_fields is None:
        card_fields = {
            "national_id": {"source": "card", "original": NID},
            "family_number": {"source": "card", "original": FAM},
        }
    return SimpleNamespace(
        national_id=national_id,
        family_number=family,
        card_fields=card_fields,
        national_id_check=check,
    )


def test_equal_to_reading_is_not_edited() -> None:
    assert edited_fields(_draft()) == []


def test_marked_edited_but_same_value_is_not_edited() -> None:
    fields = {
        "national_id": {"source": "edited", "original": NID},
        "family_number": {"source": "edited", "original": FAM},
    }
    assert edited_fields(_draft(card_fields=fields)) == []


def test_other_written_forms_of_the_reading_are_not_edited() -> None:
    assert edited_fields(_draft(national_id="١٩٩٠١٢٣٤٥٦٧٨", family="1234 a 5678901234567")) == []


def test_one_digit_changed_is_edited() -> None:
    assert edited_fields(_draft(family="1234A5678901234568")) == ["family_number"]
    assert edited_fields(_draft(national_id="199012345679")) == ["national_id"]


def test_both_changed_are_both_reported_in_order() -> None:
    assert edited_fields(_draft("199012345679", "1234A5678901234568")) == [
        "national_id",
        "family_number",
    ]


def test_typed_by_hand_with_no_reading_is_edited() -> None:
    assert edited_fields(_draft(card_fields={})) == ["national_id", "family_number"]
    nulls = {
        "national_id": {"source": "edited", "original": None},
        "family_number": {"source": "edited", "original": None},
    }
    assert edited_fields(_draft(card_fields=nulls)) == ["national_id", "family_number"]


def test_value_from_verified_mrz_is_not_edited() -> None:
    mrz = "199012340000"
    d = _draft(national_id=mrz, check={"mrz": mrz, "confirmed_value": mrz})
    assert edited_fields(d) == []


def test_mrz_alone_without_front_reading_is_not_edited() -> None:
    fields = {"family_number": {"source": "card", "original": FAM}}
    d = _draft(card_fields=fields, check={"mrz": NID, "confirmed_value": None})
    assert edited_fields(d) == []
