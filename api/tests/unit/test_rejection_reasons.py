"""Rejection reasons (docs/system.md v1.14 §6.4, specs/010 research R6). No database."""

import pytest

from app.core import rejection_reasons
from app.errors import AppError
from app.models.request import REJECTION_REASONS


def test_every_code_has_its_arabic_label() -> None:
    assert rejection_reasons.LABELS == {
        "card_unclear": "صورة البطاقة غير واضحة",
        "numbers_mismatch": "الأرقام غير مطابقة للبطاقة",
        "under_15_days": "المتبقي من الاشتراك الأول أقل من 15 يوماً",
        "active_subscription": "المشترك لديه اشتراك فعّال",
        "other": "سبب آخر",
    }
    # The same codes as the database check (migration 0013).
    assert tuple(rejection_reasons.LABELS) == REJECTION_REASONS


@pytest.mark.parametrize("note", [None, "", "   ", "ab", " ab "])
def test_other_needs_a_note_of_three_characters(note) -> None:
    with pytest.raises(AppError) as err:
        rejection_reasons.validate("other", note)
    assert (err.value.code, err.value.status) == ("rejection_note_required", 422)


def test_other_note_is_trimmed() -> None:
    assert rejection_reasons.validate("other", "  طلب مكرر  ") == "طلب مكرر"


def test_note_of_300_characters_is_accepted_and_301_refused() -> None:
    assert rejection_reasons.validate("other", "ب" * 300) == "ب" * 300
    with pytest.raises(AppError) as err:
        rejection_reasons.validate("other", "ب" * 301)
    assert err.value.code == "validation_error"


@pytest.mark.parametrize("code", ["card_unclear", "numbers_mismatch", "under_15_days"])
def test_fixed_reason_takes_no_note(code) -> None:
    assert rejection_reasons.validate(code, None) is None
    assert rejection_reasons.validate(code, "  ") is None  # blank counts as none
    with pytest.raises(AppError) as err:
        rejection_reasons.validate(code, "نص إضافي")
    assert err.value.code == "validation_error"


def test_unknown_code_is_refused() -> None:
    with pytest.raises(AppError) as err:
        rejection_reasons.validate("rude", None)
    assert err.value.code == "validation_error"


def test_label_is_the_arabic_label_or_the_note() -> None:
    assert rejection_reasons.label("card_unclear", None) == "صورة البطاقة غير واضحة"
    assert rejection_reasons.label("other", "طلب مكرر") == "طلب مكرر"
    assert rejection_reasons.label(None, None) is None
