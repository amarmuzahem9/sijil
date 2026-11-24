"""The link message text (docs/system.md v1.17 §8.4, specs/012 research R1–R2). No database.

A stand-in object carries every column a request has that could leak (national ID, family number,
readings, images, OTP); the message must hold none of them (SC-002). Synthetic values only.
"""

from types import SimpleNamespace

import pytest

from app.core import link_message

NID = "199012345678"
FAMILY = "1234A5678901234567"


def _request(**overrides):
    values = dict(
        number_label="T3C-1001",
        status="approved",
        is_deleted=False,
        type="new",
        full_name="تجربة اختبار نموذج مثال التجريبي",
        phone="07801234567",
        username="ALM03-07801234567",
        tower_name="برج 3",
        tower_code="ALM03",
        area_name="العلم",
        plan_name="PLUS",
        trial_price=20000,
        second_price=35000,
        address="حي تجريبي",
        landmark="قرب نقطة تجريبية",
        location_lat=34.7,
        location_lng=43.68,
        marketer=SimpleNamespace(name="مسوّق تجريبي"),
        # Columns that must never appear.
        national_id=NID,
        national_id_input=NID,
        submitted_national_id=NID,
        family_number=FAMILY,
        submitted_family_number=FAMILY,
        family_key=FAMILY,
        card_readings={"front": {"national_id": NID}, "back": {"family_number": FAMILY}},
        images=[SimpleNamespace(file_name="secret-front.jpg")],
    )
    values.update(overrides)
    return SimpleNamespace(**values)


GOLDEN = "\n".join(
    [
        "طلب ربط جديد | رقم الطلب: #T3C-1001",
        "الاسم: تجربة اختبار نموذج مثال التجريبي",
        "الهاتف: 07801234567",
        "اليوزر: ALM03-07801234567",
        "البرج: برج 3 (ALM03)",
        "الفئة: PLUS | التجريبي 20,000 د.ع | الثاني 35,000 د.ع",
        "العنوان: حي تجريبي، قرب نقطة تجريبية",
        "الموقع: https://maps.google.com/?q=34.7,43.68",
        "المسوّق: مسوّق تجريبي",
    ]
)


@pytest.mark.parametrize("type_", ["new", "additional", "return"])
def test_golden_text_for_each_type(type_) -> None:
    assert link_message.compose(_request(type=type_)) == GOLDEN


def test_linked_request_has_the_message() -> None:
    assert link_message.compose(_request(status="linked")) == GOLDEN


def test_return_keeps_its_historical_username() -> None:
    text = link_message.compose(_request(type="return", username="OLD-07801234567"))
    assert "اليوزر: OLD-07801234567" in text.splitlines()


@pytest.mark.parametrize(
    ("address", "landmark", "line"),
    [
        ("حي تجريبي", None, "العنوان: حي تجريبي"),
        (None, "قرب نقطة", "العنوان: قرب نقطة"),
        ("", "  ", "العنوان: —"),
        (None, None, "العنوان: —"),
        ("  حي تجريبي ", "قرب نقطة", "العنوان: حي تجريبي، قرب نقطة"),
    ],
)
def test_address_line(address, landmark, line) -> None:
    lines = link_message.compose(_request(address=address, landmark=landmark)).splitlines()
    assert lines[6] == line


@pytest.mark.parametrize(
    ("lat", "lng", "query"),
    [
        (34.7, 43.68, "34.7,43.68"),
        (33.123456789, 44.1, "33.123457,44.1"),
        (33.0, 44.0, "33,44"),
        (36.1000004, 42.0000001, "36.1,42"),
    ],
)
def test_coordinates_up_to_six_decimals(lat, lng, query) -> None:
    lines = link_message.compose(_request(location_lat=lat, location_lng=lng)).splitlines()
    assert lines[7] == f"الموقع: https://maps.google.com/?q={query}"


def test_prices_keep_thousands_separators() -> None:
    lines = link_message.compose(_request(trial_price=0, second_price=1250000)).splitlines()
    assert lines[5] == "الفئة: PLUS | التجريبي 0 د.ع | الثاني 1,250,000 د.ع"


@pytest.mark.parametrize("status", ["pending_review", "rejected"])
def test_no_message_before_acceptance(status) -> None:
    assert link_message.compose(_request(status=status)) is None


def test_no_message_for_a_deleted_request() -> None:
    assert link_message.compose(_request(is_deleted=True)) is None


def test_never_holds_identity_numbers_images_or_codes() -> None:
    text = link_message.compose(_request())
    for secret in (NID, FAMILY, "1234A", "secret-front", "رمز", "OTP"):
        assert secret not in text
    assert text.count("\n") == 8
    assert not text.endswith("\n")
