"""US5 — read-only audit viewer for the main admin (specs/002 contracts/api.md › Audit log)."""

from datetime import UTC, datetime

import pytest

from app.core.access import ADMIN_PERMISSIONS
from app.models import AuditLog
from tests.conftest import auth_header, login

BASE = "/api/admin/audit"


def _entry(db, *, actor, action="user.updated", at, target=None, before=None, after=None):
    e = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type="user",
        entity_id=str(target.id if target else 0),
        before=before,
        after=after,
        created_at=at,
    )
    db.add(e)
    db.flush()
    return e


@pytest.fixture
def main(make_user):
    return make_user("super_admin", name="المدير")


@pytest.fixture
def h(client, main):
    return auth_header(login(client, main.phone))


def test_newest_first_with_names_and_values(client, db, main, h, make_user) -> None:
    m = make_user("marketer", name="مسوّق السجل")
    old = _entry(
        db,
        actor=main,
        at=datetime(2026, 11, 20, 9, tzinfo=UTC),
        target=m,
        before={"name": "أ"},
        after={"name": "ب"},
    )
    new = _entry(
        db, actor=None, action="user.locked", at=datetime(2026, 11, 21, 9, tzinfo=UTC), target=m
    )
    items = client.get(BASE, headers=h).json()["items"]
    ids = [i["id"] for i in items]
    assert ids.index(new.id) < ids.index(old.id)
    first = next(i for i in items if i["id"] == old.id)
    assert first["actor"] == {"id": main.id, "name": "المدير", "role": "super_admin"}
    assert first["target"]["name"] == "مسوّق السجل"
    assert (first["before"], first["after"]) == ({"name": "أ"}, {"name": "ب"})
    assert next(i for i in items if i["id"] == new.id)["actor"] is None


def test_keyset_paging(client, db, main, h) -> None:
    for d in range(1, 6):
        _entry(db, actor=main, at=datetime(2026, 10, d, tzinfo=UTC))
    seen, before = [], None
    while True:
        params = {"limit": 2, "from": "2026-10-01", "to": "2026-10-05"}
        if before:
            params["before_id"] = before
        page = client.get(BASE, params=params, headers=h).json()
        seen += [i["id"] for i in page["items"]]
        if not page["has_more"]:
            assert page["next_before_id"] is None
            break
        before = page["next_before_id"]
    assert len(seen) == 5 and seen == sorted(seen, reverse=True)
    assert client.get(BASE, params={"limit": 101}, headers=h).status_code == 422


def test_baghdad_day_filter(client, db, main, h) -> None:
    # 20:30 UTC on 22 Nov = 23:30 Baghdad on 22 Nov; 21:30 UTC = 00:30 on 23 Nov.
    late = _entry(db, actor=main, at=datetime(2026, 11, 22, 20, 30, tzinfo=UTC))
    next_day = _entry(db, actor=main, at=datetime(2026, 11, 22, 21, 30, tzinfo=UTC))
    ids = [
        i["id"]
        for i in client.get(
            BASE, params={"from": "2026-11-22", "to": "2026-11-22"}, headers=h
        ).json()["items"]
    ]
    assert late.id in ids and next_day.id not in ids
    assert (
        client.get(BASE, params={"from": "2026-11-23", "to": "2026-11-22"}, headers=h).status_code
        == 422
    )


def test_actor_filter_and_actor_list(client, db, main, h, make_user) -> None:
    other = make_user("admin", name="أدمن السجل")
    mine = _entry(db, actor=main, at=datetime(2026, 9, 1, tzinfo=UTC))
    theirs = _entry(db, actor=other, at=datetime(2026, 9, 1, tzinfo=UTC))
    system = _entry(db, actor=None, at=datetime(2026, 9, 1, tzinfo=UTC))

    def ids(actor):
        return {
            i["id"] for i in client.get(BASE, params={"actor_id": actor}, headers=h).json()["items"]
        }

    assert theirs.id in ids(other.id) and mine.id not in ids(other.id)
    assert system.id in ids("system") and mine.id not in ids("system")
    assert client.get(BASE, params={"actor_id": "abc"}, headers=h).status_code == 422
    actors = client.get(f"{BASE}/actors", headers=h).json()["items"]
    assert {a["id"] for a in actors} >= {main.id, other.id}


@pytest.mark.parametrize("role", ["admin", "marketer"])
def test_only_main_admin(client, db, make_user, role) -> None:
    u = make_user(role)
    if role == "admin":
        u.permissions = list(ADMIN_PERMISSIONS)
        db.flush()
    hh = auth_header(login(client, u.phone))
    assert client.get(BASE, headers=hh).status_code == 403
    assert client.get(f"{BASE}/actors", headers=hh).status_code == 403


def test_read_only(client, h) -> None:
    for method in ("post", "put", "patch", "delete"):
        r = getattr(client, method)(BASE, headers=h)
        assert r.status_code in (404, 405)
    assert client.delete(f"{BASE}/1", headers=h).status_code in (404, 405)


# --- specs/011 T045: entries of a deleted request ---------------------------------------------


def test_entries_of_a_deleted_request_are_marked_and_unchanged(
    client, db, main, h, make_user, tmp_path, monkeypatch
) -> None:
    from app.config import get_settings
    from tests.helpers.requests import request_factory
    from tests.helpers.review import admin_with, headers_for

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    marketer = make_user("marketer")
    reviewer = admin_with(make_user, "review", "delete")
    rh = headers_for(client, reviewer)
    gone = request_factory(db, marketer, status="pending_review", national_id_input="١٩٩٠٠٠٠٠٠٠٠١")
    kept = request_factory(db, marketer, status="pending_review")
    pin = {"field": "national_id", "source": "typed", "value": "199000000077"}
    assert (
        client.post(f"/api/admin/requests/{gone.id}/pin", json=pin, headers=rh).status_code == 200
    )
    reject = {"reason": "other", "note": "نص المراجع للسجل"}
    assert (
        client.post(f"/api/admin/requests/{gone.id}/reject", json=reject, headers=rh).status_code
        == 200
    )
    assert (
        client.post(f"/api/admin/requests/{kept.id}/reject", json=reject, headers=rh).status_code
        == 200
    )
    before = {
        e["id"]: (e["action"], e["before"], e["after"])
        for e in client.get("/api/admin/audit", headers=h).json()["items"]
    }

    res = client.post(
        f"/api/admin/requests/{gone.id}/delete",
        json={"reason": "test", "confirm_number": gone.number_label},
        headers=rh,
    )
    assert res.status_code == 200, res.json()

    items = client.get("/api/admin/audit", headers=h).json()["items"]
    by_id = {e["id"]: e for e in items}
    # Old lines are byte-for-byte the same, the reject note included.
    for entry_id, old in before.items():
        e = by_id[entry_id]
        assert (e["action"], e["before"], e["after"]) == old
    # Every line about the deleted request is marked; the others are not.
    for e in items:
        if e["entity_type"] == "request" and e["entity_id"] == str(gone.number):
            assert e["entity_deleted"] is True, e["action"]
        else:
            assert e["entity_deleted"] is False, e["action"]
    actions = {
        e["action"]
        for e in items
        if e["entity_type"] == "request" and e["entity_id"] == str(gone.number)
    }
    assert {"request.numbers_pinned", "request.rejected", "request.deleted"} <= actions
