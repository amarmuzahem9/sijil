"""Deletion reasons (docs/system.md v1.15 §7.4, specs/011 data-model.md). No database."""

import pytest

from app.core import deletion_reasons
from app.errors import AppError
from app.models.request import DELETION_REASONS


def test_every_code_has_its_arabic_label_in_order() -> None:
    assert list(deletion_reasons.LABELS.items()) == [
        ("duplicate", "طلب مكرر"),
        ("test", "طلب تجريبي"),
        ("entry_error", "خطأ إدخال"),
        ("other", "سبب آخر"),
    ]
    # The same codes as the database check (migration 0014).
    assert tuple(deletion_reasons.LABELS) == DELETION_REASONS


@pytest.mark.parametrize("code", ["duplicate", "test", "entry_error", "other"])
def test_known_codes_pass(code) -> None:
    deletion_reasons.validate(code)


@pytest.mark.parametrize("code", ["", "Other", "guess", "card_unclear"])
def test_unknown_codes_are_refused(code) -> None:
    with pytest.raises(AppError) as err:
        deletion_reasons.validate(code)
    assert (err.value.code, err.value.status) == ("validation_error", 422)
