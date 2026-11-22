"""US3 — reward tiers as one list (specs/004 contracts/api.md › Reward tiers)."""

import pytest
from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import auth_header, login

URL = "/api/admin/settings/tiers"
DEFAULTS = [
    {"min_count": 0, "rate": 5000},
    {"min_count": 30, "rate": 7000},
    {"min_count": 50, "rate": 10000},
]


@pytest.fixture
def h(client, make_user, db):
    a = make_user("admin")
    a.permissions = ["settings"]
    db.flush()
    return auth_header(login(client, a.phone))


def _entries(db):
    return list(
        db.execute(select(AuditLog).where(AuditLog.action == "reward_tiers.updated")).scalars()
    )


def test_defaults_seeded(client, h) -> None:
    assert client.get(URL, headers=h).json() == {"items": DEFAULTS}


def test_replace_and_audit(client, db, h) -> None:
    new = [*DEFAULTS, {"min_count": 80, "rate": 12000}]
    r = client.put(URL, json={"items": list(reversed(new))}, headers=h)  # any order in
    assert r.status_code == 200 and r.json() == {"items": new}  # ascending out
    assert client.get(URL, headers=h).json() == {"items": new}
    [entry] = _entries(db)
    assert entry.entity_type == "reward_tiers"
    assert entry.before == {"tiers": DEFAULTS} and entry.after == {"tiers": new}


def test_unchanged_list_writes_nothing(client, db, h) -> None:
    assert client.put(URL, json={"items": DEFAULTS}, headers=h).status_code == 200
    assert _entries(db) == []


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ([], "أضف شريحة واحدة على الأقل"),
        ([{"min_count": 5, "rate": 5000}], "الشريحة الأولى يجب أن تبدأ من 0"),
        (
            [{"min_count": 0, "rate": 1}, {"min_count": 0, "rate": 2}],
            "أقل عدد يجب أن يكون تصاعدياً بلا تكرار",
        ),
        ([{"min_count": 0, "rate": 0}], "سعر المشترك يجب أن يكون من 1 إلى 10,000,000"),
    ],
)
def test_invalid_lists(client, db, h, items, message) -> None:
    r = client.put(URL, json={"items": items}, headers=h)
    assert r.json() == {"code": "invalid_tiers", "message": message}
    assert client.get(URL, headers=h).json() == {"items": DEFAULTS}  # unchanged


@pytest.mark.parametrize(
    "body",
    [
        {"items": [{"min_count": "0", "rate": 5000}]},
        {"items": [{"min_count": 0, "rate": 5000.5}]},
        {"items": [{"min_count": 0, "rate": 5000, "extra": 1}]},
        {"tiers": []},
    ],
)
def test_malformed_bodies(client, h, body) -> None:
    r = client.put(URL, json=body, headers=h)
    assert (r.status_code, r.json()["code"]) == (422, "validation_error")


def test_permission(client, make_user, db) -> None:
    a = make_user("admin")
    a.permissions = ["commissions", "reports"]
    db.flush()
    for user in (a, make_user("marketer")):
        hh = auth_header(login(client, user.phone))
        assert client.get(URL, headers=hh).status_code == 403
        assert client.put(URL, json={"items": DEFAULTS}, headers=hh).status_code == 403
