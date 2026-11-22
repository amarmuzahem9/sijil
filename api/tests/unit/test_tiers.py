"""Reward tier list rules (specs/004 data-model.md › reward_tiers, research.md R5)."""

import pytest

from app.errors import AppError
from app.services.settings_service import validate_tiers


def _message(items) -> str:
    with pytest.raises(AppError) as exc:
        validate_tiers(items)
    assert exc.value.code == "invalid_tiers"
    return exc.value.message


def test_defaults_are_valid_and_sorted_copy_returned() -> None:
    items = [(0, 5000), (30, 7000), (50, 10000)]
    assert validate_tiers(items) == items


def test_single_tier_from_zero_is_valid() -> None:
    assert validate_tiers([(0, 1)]) == [(0, 1)]


def test_empty_list() -> None:
    assert _message([]) == "أضف شريحة واحدة على الأقل"


def test_too_many() -> None:
    assert _message([(i, 1) for i in range(21)]) == "الحد الأقصى 20 شريحة"


def test_first_must_start_at_zero() -> None:
    assert _message([(5, 5000), (30, 7000)]) == "الشريحة الأولى يجب أن تبدأ من 0"


def test_duplicates_refused() -> None:
    assert _message([(0, 1), (30, 2), (30, 3)]) == "أقل عدد يجب أن يكون تصاعدياً بلا تكرار"


def test_any_input_order_is_sorted() -> None:
    """Rows may be added in any order on screen; the stored list is ascending."""
    assert validate_tiers([(50, 3), (0, 1), (30, 2)]) == [(0, 1), (30, 2), (50, 3)]


@pytest.mark.parametrize("count", [-1, 10_001])
def test_count_range(count) -> None:
    assert _message([(0, 1), (count, 2)]) == "أقل عدد يجب أن يكون من 0 إلى 10,000"


@pytest.mark.parametrize("rate", [0, -5, 10_000_001])
def test_rate_range(rate) -> None:
    assert _message([(0, rate)]) == "سعر المشترك يجب أن يكون من 1 إلى 10,000,000"
