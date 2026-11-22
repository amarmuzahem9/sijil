import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.draft import TEXT_LIMITS
from app.services.draft_validation import MISSING_ORDER, missing

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "draft_validation_cases.json").read_text("utf-8")
)
FIELDS = (
    "first_name",
    "father_name",
    "grandfather_name",
    "great_grandfather_name",
    "surname",
    "mother_first_name",
    "mother_second_name",
    "mother_third_name",
    "mother_surname",
    "national_id",
    "family_number",
    "location_lat",
    "location_lng",
    "address",
    "landmark",
    "area_id",
    "tower_id",
    "plan_id",
    "phone_input",
    "no_surname",
)


def _draft(values: dict) -> SimpleNamespace:
    return SimpleNamespace(**{name: values.get(name) for name in FIELDS})


@pytest.mark.parametrize("case", FIXTURE["drafts"], ids=[c["note"] for c in FIXTURE["drafts"]])
def test_missing(case: dict) -> None:
    assert missing(_draft(case["draft"]), case["images"]) == case["missing"]


def test_order_matches_fixture() -> None:
    assert list(MISSING_ORDER) == FIXTURE["missing_order"]


def test_limits_match_fixture() -> None:
    # The same limits are enforced by the client mirror, the service and migration 0005.
    assert TEXT_LIMITS == FIXTURE["limits"]


def test_empty_draft_lists_everything_in_page_order() -> None:
    result = missing(_draft({}), [])
    assert [item["field"] for item in result] == list(MISSING_ORDER)
    assert {item["code"] for item in result} == {"required"}
