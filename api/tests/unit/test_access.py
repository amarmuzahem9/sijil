"""Page → permission map against the fixture shared with the web (specs/002 data-model.md)."""

import json
from pathlib import Path

import pytest

from app.core.access import ADMIN_PERMISSIONS, PAGE_ACCESS, can_access, normalize_permissions

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "page_access.json").read_text("utf-8")
)


def test_page_rules_match_fixture() -> None:
    expected = {
        p["key"]: (p["access"] if isinstance(p["access"], str) else tuple(p["access"]))
        for p in FIXTURE["pages"]
    }
    assert PAGE_ACCESS == expected


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda c: f"{c['role']}:{c['permissions']}")
def test_visible_pages(case) -> None:
    visible = [p for p in PAGE_ACCESS if can_access(case["role"], case["permissions"], p)]
    assert visible == case["visible"]


def test_normalize_permissions_dedupes_and_orders() -> None:
    assert normalize_permissions(["reports", "review", "reports"]) == ["review", "reports"]
    assert normalize_permissions(list(reversed(ADMIN_PERMISSIONS))) == list(ADMIN_PERMISSIONS)


def test_normalize_permissions_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        normalize_permissions(["review", "delete_everything"])


def test_delete_permission() -> None:
    """specs/011 research R7: «حذف مشترك» is the last admin permission; the main admin holds it."""
    from app.core.access import has_any_permission

    assert ADMIN_PERMISSIONS[-2:] == ("commissions", "delete")
    assert normalize_permissions(["delete", "review"]) == ["review", "delete"]
    assert has_any_permission("super_admin", [], ["delete"]) is True
    assert has_any_permission("admin", ["review"], ["delete"]) is False
    assert has_any_permission("admin", ["delete"], ["delete"]) is True
    assert has_any_permission("marketer", ["delete"], ["delete"]) is False
