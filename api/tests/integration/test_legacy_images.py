"""Legacy card images for review (specs/014 US3: FR-016; research R13; §13). Review admins only,
every open logged. Generated images only."""

import logging
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import ImageAccessLog, LegacyImage
from tests.helpers.card_images import scenario_jpeg
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.review import admin_with, headers_for


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def sub(db, make_user):
    return legacy_subscriber(db, make_user("super_admin"), phone="07811115555")


def _image(db, uploads, sub, side="front", *, write=True) -> LegacyImage:
    name = f"{uuid.uuid4().hex}.jpg"
    if write:
        (uploads / name).write_bytes(scenario_jpeg("clear_front"))
    image = LegacyImage(
        id=uuid.uuid4(),
        legacy_subscriber_id=sub.id,
        side=side,
        file_name=name,
        size_bytes=1000,
        width=100,
        height=60,
    )
    db.add(image)
    db.flush()
    return image


def _get(client, user, image_id):
    return client.get(f"/api/admin/legacy-images/{image_id}", headers=headers_for(client, user))


def _log(db):
    return db.scalars(select(ImageAccessLog).order_by(ImageAccessLog.id)).all()


@pytest.mark.parametrize("who", ["super_admin", "review"])
def test_review_admins_open_it_and_it_is_logged(client, db, uploads, make_user, sub, who) -> None:
    user = make_user("super_admin") if who == "super_admin" else admin_with(make_user, "review")
    image = _image(db, uploads, sub, "back")
    res = _get(client, user, image.id)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert "no-store" in res.headers.get("cache-control", "")
    (entry,) = _log(db)
    assert (entry.user_id, entry.image_id, entry.legacy_subscriber_id) == (
        user.id,
        image.id,
        sub.id,
    )
    assert (entry.request_id, entry.draft_id, entry.side, entry.purpose) == (
        None,
        None,
        "back",
        "view",
    )


@pytest.mark.parametrize("who", [("admin", ["reports"]), ("admin", ["link"]), ("marketer", [])])
def test_others_get_404_and_no_log(client, db, uploads, make_user, sub, who) -> None:
    role, perms = who
    user = make_user(role)
    user.permissions = perms
    image = _image(db, uploads, sub)
    res = _get(client, user, image.id)
    assert res.status_code == 404
    assert res.json()["code"] == "image_not_found"
    assert _log(db) == []


def test_missing_file_is_404_without_the_path_in_the_log(
    client, db, uploads, make_user, sub, caplog
) -> None:
    image = _image(db, uploads, sub, write=False)
    caplog.set_level(logging.INFO)
    res = _get(client, make_user("super_admin"), image.id)
    assert res.status_code == 404
    assert image.file_name not in caplog.text
    assert _log(db) == []


def test_unknown_id_is_404(client, make_user) -> None:
    assert _get(client, make_user("super_admin"), uuid.uuid4()).status_code == 404


def test_a_request_image_id_does_not_open_here(client, db, uploads, make_user) -> None:
    """The two image routes are separate: a request image is not a legacy image."""
    from app.core.timeutil import utc_now
    from app.models import RequestImage
    from tests.helpers.requests import request_factory

    request = request_factory(db, make_user("marketer"))
    name = f"{uuid.uuid4().hex}.jpg"
    (uploads / name).write_bytes(scenario_jpeg("clear_front"))
    image = RequestImage(
        id=uuid.uuid4(),
        request_id=request.id,
        side="front",
        file_name=name,
        size_bytes=1,
        width=1,
        height=1,
        uploaded_by=request.marketer_id,
        created_at=utc_now(),
    )
    db.add(image)
    db.flush()
    assert _get(client, make_user("super_admin"), image.id).status_code == 404
