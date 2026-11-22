"""US4 — the drafts list, deleting a draft with its files, and orphan cleanup
(specs/005 research.md R8, data-model.md › audit_log, FR-018, FR-019)."""

import io
import os
import time
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app import cli
from app.config import get_settings
from app.models import AuditLog, Draft, DraftImage, ImageAccessLog
from app.services import image_store
from tests.conftest import auth_header, login


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 500), (10, 120, 60)).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _h(response) -> dict[str, str]:
    headers = auth_header(response)
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


@pytest.fixture
def owner(client, make_user):
    user = make_user("marketer")
    return user, _h(login(client, user.phone))


def _draft(client, h, changes=None) -> str:
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": changes or {}}, headers=h)
    assert res.status_code == 201
    return draft_id


def _upload(client, h, draft_id, side) -> dict:
    res = client.post(
        f"/api/drafts/{draft_id}/images/{side}",
        files={"file": ("x.jpg", _jpeg(), "image/jpeg")},
        headers=h,
    )
    assert res.status_code == 200
    return res.json()


# --- list ------------------------------------------------------------------------------------


def test_list_only_own_drafts_newest_first(client, frozen_clock, make_user, owner):
    from datetime import timedelta

    h = owner[1]
    older = _draft(client, h, {"first_name": "مشترك أول"})
    frozen_clock.advance(timedelta(minutes=5))
    newer = _draft(client, h, {"first_name": "مشترك ثاني", "phone_input": "0780 123 4567"})
    other = _h(login(client, make_user("marketer").phone))
    _draft(client, other, {"first_name": "مشترك غيري"})

    items = client.get("/api/drafts", headers=h).json()["items"]
    assert [i["id"] for i in items] == [newer, older]
    first = items[0]
    assert first["full_name"] == "مشترك ثاني"
    assert first["phone_normalized"] == "07801234567"
    assert first["has_images"] is False
    assert first["missing_count"] == 16  # 18 items minus the first name and the phone
    assert set(first) == {
        "id",
        "full_name",
        "tower_code",
        "phone_normalized",
        "updated_at",
        "missing_count",
        "has_images",
    }

    # Editing the older one moves it to the top.
    frozen_clock.advance(timedelta(minutes=5))
    client.patch(
        f"/api/drafts/{older}", json={"version": 1, "changes": {"address": "حي"}}, headers=h
    )
    assert client.get("/api/drafts", headers=h).json()["items"][0]["id"] == older


def test_list_counts_images(client, owner):
    h = owner[1]
    draft_id = _draft(client, h)
    _upload(client, h, draft_id, "front")
    item = client.get("/api/drafts", headers=h).json()["items"][0]
    assert item["has_images"] is True
    assert item["missing_count"] == 17


@pytest.mark.parametrize(
    "q,expected",
    [
        ("مشترك", 2),
        ("ثاني", 1),
        ("07801234567", 1),
        ("1234567", 1),
        ("٠٧٨٠١٢٣", 1),  # Arabic digits
        ("غير موجود", 0),
        ("   ", 2),
    ],
)
def test_search_by_name_or_phone(client, owner, q, expected):
    h = owner[1]
    _draft(client, h, {"first_name": "مشترك أول"})
    _draft(client, h, {"first_name": "مشترك ثاني", "phone_input": "07801234567"})
    res = client.get("/api/drafts", params={"q": q}, headers=h)
    assert res.status_code == 200
    assert len(res.json()["items"]) == expected


@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_admins_get_403_on_list(client, make_user, role):
    assert (
        client.get("/api/drafts", headers=_h(login(client, make_user(role).phone))).status_code
        == 403
    )


# --- delete ----------------------------------------------------------------------------------


def test_delete_removes_rows_files_and_audits_without_card_data(client, db, owner, uploads):
    user, h = owner
    draft_id = _draft(
        client,
        h,
        {
            "first_name": "مشترك تجريبي",
            "national_id": "199012345678",
            "family_number": "A1B2C3",
            "phone_input": "07801234567",
        },
    )
    _upload(client, h, draft_id, "front")
    body = _upload(client, h, draft_id, "back")
    image_id = body["images"]["front"]["id"]
    client.get(f"/api/draft-images/{image_id}", headers=h)  # one access log row
    names = set(db.scalars(select(DraftImage.file_name)).all())
    assert {p.name for p in uploads.iterdir()} == names and len(names) == 2

    res = client.delete(f"/api/drafts/{draft_id}", headers=h)
    assert res.status_code == 204

    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is None
    assert db.scalars(select(DraftImage)).all() == []
    assert list(uploads.iterdir()) == []

    entry = db.scalars(select(AuditLog).where(AuditLog.action == "draft.deleted")).one()
    assert entry.actor_id == user.id
    assert entry.entity_type == "draft"
    assert entry.entity_id == draft_id
    assert set(entry.before) == {
        "created_at",
        "updated_at",
        "tower_code",
        "image_count",
        "missing_count",
    }
    assert entry.before["image_count"] == 2
    text = str(entry.before) + str(entry.after)
    for secret in ("مشترك تجريبي", "199012345678", "A1B2C3", "07801234567", *names):
        assert secret not in text

    # The access history survives the deletion (Principle III).
    assert len(db.scalars(select(ImageAccessLog)).all()) == 1

    assert client.get(f"/api/drafts/{draft_id}", headers=h).status_code == 404
    assert client.get(f"/api/drafts/{draft_id}/version", headers=h).status_code == 404
    assert client.delete(f"/api/drafts/{draft_id}", headers=h).status_code == 404


def test_other_marketer_cannot_delete(client, db, make_user, owner, uploads):
    draft_id = _draft(client, owner[1])
    _upload(client, owner[1], draft_id, "front")
    other = _h(login(client, make_user("marketer").phone))
    res = client.delete(f"/api/drafts/{draft_id}", headers=other)
    assert res.status_code == 404
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)) is not None
    assert len(list(uploads.iterdir())) == 1
    assert db.scalars(select(AuditLog).where(AuditLog.action == "draft.deleted")).all() == []


# --- prune-uploads ---------------------------------------------------------------------------


def _age(path: Path, hours: float) -> None:
    past = time.time() - hours * 3600
    os.utime(path, (past, past))


def test_prune_removes_only_old_unreferenced_files(client, db, owner, uploads, monkeypatch):
    draft_id = _draft(client, owner[1])
    _upload(client, owner[1], draft_id, "front")
    referenced = db.scalars(select(DraftImage.file_name)).one()
    old_orphan = uploads / f"{uuid.uuid4().hex}.jpg"
    fresh_orphan = uploads / f"{uuid.uuid4().hex}.jpg"
    old_temp = uploads / f"{uuid.uuid4().hex}.jpg.part"
    foreign = uploads / "keep-me.txt"
    for p in (old_orphan, fresh_orphan, old_temp, foreign):
        p.write_bytes(b"x")
    for p in (uploads / referenced, old_orphan, old_temp, foreign):
        _age(p, 2)

    # The CLI opens its own session; point it at the test transaction.
    monkeypatch.setattr(cli, "get_sessionmaker", lambda: lambda: _NoClose(db))
    assert cli.main(["prune-uploads"]) == 0

    left = {p.name for p in uploads.iterdir()}
    assert left == {referenced, fresh_orphan.name, foreign.name}


def test_prune_helper_returns_removed_names(uploads):
    orphan = uploads / f"{uuid.uuid4().hex}.jpg"
    orphan.write_bytes(b"x")
    _age(orphan, 3)
    assert image_store.prune_orphans(set()) == [orphan.name]


class _NoClose:
    """Context-manager wrapper that leaves the test session open."""

    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, *exc):
        return False
