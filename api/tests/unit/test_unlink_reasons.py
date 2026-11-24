"""The fixed reasons to undo «تم الربط» (docs/system.md v1.18 §6.5, specs/013 research R4)."""

import pytest

from app.core import unlink_reasons
from app.errors import AppError


def test_labels_are_the_owner_list() -> None:
    assert unlink_reasons.LABELS == {
        "not_linked_in_sas": "لم يُربط فعلياً في SAS",
        "by_mistake": "ضُغط بالخطأ",
        "other_request_linked": "ربط طلب آخر بدله",
        "other": "سبب آخر",
    }


@pytest.mark.parametrize("code", list(unlink_reasons.LABELS))
def test_validate_accepts_each_code(code: str) -> None:
    unlink_reasons.validate(code)


@pytest.mark.parametrize("code", ["", "mistake", "سبب آخر", "OTHER"])
def test_validate_refuses_anything_else(code: str) -> None:
    with pytest.raises(AppError) as err:
        unlink_reasons.validate(code)
    assert (err.value.code, err.value.status) == ("validation_error", 422)
