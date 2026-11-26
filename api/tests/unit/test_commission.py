"""The tier rule (docs/system.md v1.23 §9, specs/017 research R1), from the shared fixture."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.core import commission

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "commission_tier_cases.json").read_text("utf-8")
)


def _tiers(name: str) -> list[tuple[int, int]]:
    return [tuple(t) for t in FIXTURE["tier_sets"][name]]


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: f"{c['tiers']}:{c['count']}")
def test_tier_amount_and_next(case) -> None:
    tiers = _tiers(case["tiers"])
    assert commission.tier_for(case["count"], tiers) == (case["min"], case["rate"])
    assert commission.amount(case["count"], tiers) == case["amount"]
    expected_next = tuple(case["next"]) if case["next"] else None
    assert commission.next_tier(case["count"], tiers) == expected_next


def test_tiers_in_any_order() -> None:
    tiers = list(reversed(_tiers("default")))
    assert commission.tier_for(30, tiers) == (30, 7000)
    assert commission.next_tier(30, tiers) == (20, 10000)


def test_negative_count_refused() -> None:
    with pytest.raises(ValueError):
        commission.tier_for(-1, _tiers("default"))


def test_no_tiers_refused() -> None:
    with pytest.raises(ValueError):
        commission.tier_for(3, [])


def test_month_key_round_trip() -> None:
    assert commission.parse_month("2026-10") == date(2026, 10, 1)
    assert commission.month_key(date(2026, 10, 1)) == "2026-10"
    assert commission.month_key(date(2026, 1, 17)) == "2026-01"


@pytest.mark.parametrize(
    "value", ["2026-13", "26-10", "2026-1", "2026-00", "", "2026/10", "٢٠٢٦-١٠"]
)
def test_bad_month_refused(value: str) -> None:
    with pytest.raises(ValueError):
        commission.parse_month(value)
