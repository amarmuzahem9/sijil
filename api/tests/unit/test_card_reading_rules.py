"""Rules for one side of a card reading (specs/006 research R6, R7; tasks T011).

The raw detections are synthetic: they rebuild the *shapes* seen in step 0 (a phantom front
inside a back photo, a back detected twice, an unreadable front, an `O` in a family number)
with made-up names and numbers. No real card data.
"""

import pytest

from app.core.card_reading import (
    mrz_check_digit,
    mrz_national_id,
    mrz_verified,
    normalize_family_number,
)
from app.services.card_reading_rules import evaluate_side

NID = "199912345678"
DOC = "A12345678"


def front(second_pass=0.94, box=(10, 10, 900, 570), fields=None, confidence=0.95):
    if fields is None:
        fields = {
            "name": "مشترك",
            "dad": "تجريبي",
            "gf": "اختبار",
            "last": "الوهمي",
            "mom": "أم",
            "gm": "تجريبية",
            "gn": "ذكر",
            "id": NID,
            "id2": DOC,
        }
    return {
        "class": "iraq id card",
        "confidence": confidence,
        "second_pass": second_pass,
        "box": list(box),
        "orientation": "NORMAL",
        "fields": {k: {"text": v, "confidence": 0.97} for k, v in fields.items()},
        "mrz": None,
        "error": None,
    }


def mrz(number=DOC, nid=NID, composite=True, birth=True):
    return {
        "mrz_type": "TD1",
        "number": number,
        "optional1": nid + "<<<",
        "date_of_birth": "990101",
        "expiration_date": "300101",
        "sex": "M",
        "valid_number": True,
        "valid_date_of_birth": birth,
        "valid_expiration_date": True,
        "valid_composite": composite,
    }


def back(
    second_pass=0.85,
    box=(10, 10, 900, 570),
    family="1064L00M1234567890",
    zone=None,
    confidence=0.85,
):
    fields = {"city": {"text": "مدينة تجريبية", "confidence": 0.93}}
    if family is not None:
        fields["nu_f"] = {"text": family, "confidence": 0.99}
    return {
        "class": "back",
        "confidence": confidence,
        "second_pass": second_pass,
        "box": list(box),
        "orientation": "NORMAL",
        "fields": fields,
        "mrz": mrz() if zone is None else zone,
        "error": None,
    }


def raw(*detections):
    return {"duration_ms": 3000, "detections": list(detections)}


# --- outcomes ---------------------------------------------------------------------------------


def test_clear_front_is_done_with_its_fields() -> None:
    out = evaluate_side(raw(front()), "front")
    assert out.state == "done" and out.reason is None
    assert out.result["fields"]["name"]["text"] == "مشترك"
    assert out.result["surname_empty"] is False


def test_front_without_surname_field_flags_surname_empty() -> None:
    fields = {
        "name": "مشترك",
        "dad": "تجريبي",
        "gf": "اختبار",
        "mom": "أم",
        "gm": "تجريبية",
        "id": NID,
    }
    out = evaluate_side(raw(front(fields=fields)), "front")
    assert out.state == "done"
    assert out.result["surname_empty"] is True


def test_clear_back_is_done_with_family_number_and_verified_zone() -> None:
    out = evaluate_side(raw(back()), "back")
    assert out.state == "done"
    assert out.result["family_number"]["normalized"] == "1064L00M1234567890"
    assert out.result["mrz"]["verified"] is True
    assert out.result["mrz"]["national_id"] == NID
    assert out.result["mrz"]["document_number"] == DOC


def test_phantom_front_without_fields_beside_a_back_is_ignored() -> None:
    # Step 0, photo 1: a "front" at 0.518 / second pass 0.876 with no fields, beside the back.
    phantom = front(second_pass=0.876, confidence=0.518, box=(600, 700, 980, 990), fields={})
    out = evaluate_side(raw(back(), phantom), "back")
    assert out.state == "done"


def test_high_confidence_second_front_without_fields_is_a_second_document() -> None:
    second = front(second_pass=0.92, box=(1000, 10, 1900, 570), fields={})
    out = evaluate_side(raw(front(), second), "front")
    assert (out.state, out.reason) == ("reshoot", "multiple")


def test_second_detection_with_readable_fields_is_a_second_document() -> None:
    second = front(
        second_pass=0.60, box=(1000, 10, 1900, 570), fields={"name": "آخر", "dad": "تجريبي"}
    )
    out = evaluate_side(raw(front(), second), "front")
    assert (out.state, out.reason) == ("reshoot", "multiple")


def test_same_back_twice_with_same_document_number_is_one_card() -> None:
    # Step 0, photo 22: the same back detected twice, far apart boxes, same MRZ number.
    first = back(box=(10, 10, 900, 570), family=None)
    second = back(box=(30, 600, 920, 1160))
    out = evaluate_side(raw(first, second), "back")
    assert out.state == "done"
    # The detection with more readable fields (the family number) is kept.
    assert out.result["family_number"]["normalized"] == "1064L00M1234567890"


def test_heavily_overlapping_detections_are_one_card() -> None:
    first = front(box=(10, 10, 900, 570))
    second = front(box=(40, 30, 920, 590), second_pass=0.95)
    out = evaluate_side(raw(first, second), "front")
    assert out.state == "done"


def test_nothing_detected_is_no_card() -> None:
    out = evaluate_side(raw(), "front")
    assert (out.state, out.reason) == ("reshoot", "no_card")


def test_low_second_pass_only_is_no_card() -> None:
    # Step 0, photo 21: a weak "car" and a weak front, both below the thresholds.
    weak_front = front(second_pass=0.0, confidence=0.269, fields={})
    car = {**front(fields={}), "class": "car", "confidence": 0.409, "second_pass": 0.345}
    out = evaluate_side(raw(car, weak_front), "front")
    assert (out.state, out.reason) == ("reshoot", "no_card")


def test_only_the_other_side_is_wrong_side() -> None:
    assert evaluate_side(raw(back()), "front").reason == "wrong_side"
    assert evaluate_side(raw(front()), "back").reason == "wrong_side"


def test_another_document_alone_is_not_unified() -> None:
    licence = {**front(fields={}), "class": "drive", "confidence": 0.6, "second_pass": 0.7}
    out = evaluate_side(raw(licence), "front")
    assert (out.state, out.reason) == ("reshoot", "not_unified")


def test_another_document_beside_a_card_is_ignored() -> None:
    licence = {
        **front(fields={}),
        "class": "drive",
        "confidence": 0.6,
        "second_pass": 0.7,
        "box": [1000, 10, 1900, 570],
    }
    assert evaluate_side(raw(front(), licence), "front").state == "done"


def test_detection_with_reader_error_still_counts_as_the_card() -> None:
    broken = {**front(fields={}), "error": "RuntimeError"}
    out = evaluate_side(raw(broken), "front")
    assert out.state == "done"
    assert out.result["fields"] == {}


# --- family number (R6.6) ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1066LOM12345678901", "1066L0M12345678901"),  # step 0, card 8: O read for zero
        ("1064l00m 1234567890", "1064L00M1234567890"),
        ("1064E9296082343092", "1064E9296082343092"),
        ("1O64L00M1234567890", "1064L00M1234567890"),
        ("", None),
        (None, None),
        ("1064L00M12345", None),  # too short
        ("10641000M234567890", None),  # no series letter
        ("١٠٦٤L00M1234567890", None),  # non-Latin digits are not guessed
    ],
)
def test_normalize_family_number(text, expected) -> None:
    assert normalize_family_number(text) == expected


def test_unreadable_family_number_is_kept_raw_but_not_normalized() -> None:
    out = evaluate_side(raw(back(family="10641000")), "back")
    assert out.state == "done"
    assert out.result["family_number"] == {
        "text": "10641000",
        "normalized": None,
        "confidence": 0.99,
    }


# --- MRZ verification (R7) --------------------------------------------------------------------


def test_mrz_check_digit_matches_icao_example() -> None:
    # ICAO 9303 specimen document number.
    assert mrz_check_digit("L898902C3") == "6"


@pytest.mark.parametrize(
    "zone,verified",
    [
        (mrz(), True),
        (mrz(composite=False), False),
        (mrz(composite=None), False),
        (mrz(birth=False), False),
        ({**mrz(), "mrz_type": "TD3"}, False),
        (None, False),
    ],
)
def test_mrz_verified(zone, verified) -> None:
    assert mrz_verified(zone) is verified
    assert (mrz_national_id(zone) == NID) is verified


def test_unverified_zone_gives_no_national_id_in_the_result() -> None:
    out = evaluate_side(raw(back(zone=mrz(composite=None))), "back")
    assert out.result["mrz"]["verified"] is False
    assert out.result["mrz"]["national_id"] is None


# --- back fields (owner change; research R13, FR-026–FR-028) -----------------------------------

from datetime import date  # noqa: E402

from app.core.arabic_name import InvalidArabicName, clean_place_text  # noqa: E402
from app.services.card_reading_rules import resolve_back_fields  # noqa: E402

TODAY = date(2026, 11, 23)


def raw_back(**overrides):
    base = {
        "mrz_birth": "990101",
        "mrz_expiry": "300101",
        "birth_place": {"text": "حي تجريبي-بغداد", "confidence": 0.93},
        "issue": ["2020/01/02", "2020/0l/02"],
        "expiry": ["2030/01/01"],
        "birth": ["1999/01/01"],
        "authority": {"text": "مديرية الجنسية والمعلومات المدنيه", "confidence": 0.9},
    }
    return {**base, **overrides}


def values(out):
    return {field: p["value"] for field, p in out.items()}


def test_clear_back_fields_are_accepted() -> None:
    out = resolve_back_fields(raw_back(), NID, TODAY)
    assert values(out) == {
        "birth_date": date(1999, 1, 1),
        "expiry_date": date(2030, 1, 1),
        "issue_date": date(2020, 1, 2),
        "birth_place": "حي تجريبي-بغداد",
        "issuing_authority": "مديرية الجنسية والمعلومات المدنية",
    }
    assert out["birth_date"]["from"] == "mrz" and out["expiry_date"]["from"] == "mrz"
    assert out["issue_date"]["from"] == "back"
    assert out["birth_date"]["original"] == "1999-01-01"


def test_birth_century_comes_from_the_national_id() -> None:
    out = resolve_back_fields(raw_back(mrz_birth="050314"), "200512345678", TODAY)
    assert out["birth_date"]["value"] == date(2005, 3, 14)
    out = resolve_back_fields(raw_back(mrz_birth="530101"), "195312345678", TODAY)
    assert out["birth_date"]["value"] == date(1953, 1, 1)


def test_printed_birth_needs_two_agreeing_readings_and_the_id_year() -> None:
    two = raw_back(mrz_birth=None, birth=["1999/01/01", "1999/07/01", "1999/01/01"])
    assert resolve_back_fields(two, NID, TODAY)["birth_date"]["value"] == date(1999, 1, 1)
    one = raw_back(mrz_birth=None, birth=["1999/01/01", "1999/07/01"])
    assert resolve_back_fields(one, NID, TODAY)["birth_date"]["value"] is None
    wrong_year = raw_back(mrz_birth=None, birth=["1998/01/01", "1998/01/01"])
    out = resolve_back_fields(wrong_year, NID, TODAY)
    assert out["birth_date"]["value"] is None
    assert out["birth_date"]["original"] == "1998/01/01"  # the raw reading is kept


def test_issue_date_must_match_the_expiry() -> None:
    out = resolve_back_fields(raw_back(issue=["2021/05/05"]), NID, TODAY)
    assert out["issue_date"]["value"] is None
    assert out["issue_date"]["original"] == "2021/05/05"
    assert out["expiry_date"]["value"] == date(2030, 1, 1)


def test_printed_expiry_needs_a_matching_printed_issue() -> None:
    both = raw_back(mrz_expiry=None, expiry=["2034/13/40", "2030/01/01"])
    out = resolve_back_fields(both, NID, TODAY)
    assert out["expiry_date"]["value"] == date(2030, 1, 1)
    assert out["expiry_date"]["from"] == "back"
    assert out["issue_date"]["value"] == date(2020, 1, 2)
    alone = raw_back(mrz_expiry=None, issue=["2021/05/05"])
    out = resolve_back_fields(alone, NID, TODAY)
    assert out["expiry_date"]["value"] is None and out["issue_date"]["value"] is None


def test_authority_is_snapped_only_when_similar() -> None:
    far = raw_back(authority={"text": "نص آخر تماما", "confidence": 0.9})
    out = resolve_back_fields(far, NID, TODAY)
    assert out["issuing_authority"] == {
        "value": None,
        "original": "نص آخر تماما",
        "confidence": 0.9,
        "from": "back",
    }


def test_place_of_birth_rule() -> None:
    assert clean_place_text("  تكريت - صلاح  الدين ") == "تكريت-صلاح الدين"
    assert clean_place_text("بغداد/الكرخ") == "بغداد/الكرخ"
    assert clean_place_text("") is None
    for bad in ("Baghdad", "بغداد 1", "-بغداد", "بغداد--الكرخ"):
        with pytest.raises(InvalidArabicName):
            clean_place_text(bad)
    out = resolve_back_fields(
        raw_back(birth_place={"text": "Tikrit", "confidence": 0.5}), NID, TODAY
    )
    assert out["birth_place"]["value"] is None and out["birth_place"]["original"] == "Tikrit"


def test_nothing_read_gives_nothing() -> None:
    assert resolve_back_fields(None, NID, TODAY) == {}


@pytest.mark.parametrize(
    "read,expected",
    [
        # Shapes seen on real cards, with generic place names.
        ("بلدصلاح الدين", "بلد-صلاح الدين"),
        ("تكريتصلاح الدين", "تكريت-صلاح الدين"),
        ("حي تجريبي ا الكرخ ا بغداد", "حي تجريبي/الكرخ/بغداد"),
        ("العلم-تكريت-صلاح الدين", "العلم-تكريت-صلاح الدين"),  # already right
        ("مدينة تجريبية", "مدينة تجريبية"),
        ("بغدادي", "بغدادي"),  # a word that merely starts with a place name is left alone
    ],
)
def test_place_separators_are_restored(read, expected) -> None:
    from app.core.card_reading import fix_place_separators

    assert clean_place_text(fix_place_separators(read)) == expected


@pytest.mark.parametrize(
    "read,filled",
    [
        ("يدع ي", False),  # staging: a few stray letters
        ("مدينة تجريبية", False),  # no known governorate or city
        ("حي تجريبي-بغداد", True),
        ("العلم تكريت صلاح الدين", True),
        ("كرمه-فلوجه-الأنبار", True),  # hamza spelling folds to the known «الانبار»
        ("بغداد", False),  # too short to be a full place of birth
    ],
)
def test_place_of_birth_needs_length_and_a_known_place(read, filled) -> None:
    out = resolve_back_fields(raw_back(birth_place={"text": read, "confidence": 0.9}), NID, TODAY)
    assert (out["birth_place"]["value"] is not None) is filled
    assert out["birth_place"]["original"]  # the raw reading is always kept
