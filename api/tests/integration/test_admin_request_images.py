"""Request images for review (specs/010 US1: FR-005; research R9). Each open is logged.
Synthetic images only."""

import logging
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.timeutil import utc_now
from app.models import ImageAccessLog, RequestImage
from tests.helpers.card_images import scenario_jpeg
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for, pending_request


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def _image(db, uploads, request, side="front", *, write=True) -> RequestImage:
    name = f"{uuid.uuid4().hex}.jpg"
    if write:
        (uploads / name).write_bytes(scenario_jpeg("clear_front"))
    image = RequestImage(
        id=uuid.uuid4(),
        request_id=request.id,
        side=side,
        file_name=name,
        size_bytes=1000,
        width=100,
        height=60,
        uploaded_by=request.marketer_id,
        created_at=utc_now(),
    )
    db.add(image)
    db.flush()
    return image


def _get(client, headers, image_id):
    return client.get(f"/api/admin/request-images/{image_id}", headers=headers)


def _log(db):
    return db.scalars(select(ImageAccessLog).order_by(ImageAccessLog.id)).all()


def test_review_admin_opens_a_request_image_and_it_is_logged(
    client, db, uploads, make_user, marketer
) -> None:
    admin = admin_with(make_user, "review")
    request = pending_request(db, marketer, [("numbers_edited", None, {"fields": []})])
    image = _image(db, uploads, request, "back")

    res = _get(client, headers_for(client, admin), image.id)

    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert "no-store" in res.headers.get("cache-control", "")
    (entry,) = _log(db)
    assert (entry.user_id, entry.image_id, entry.request_id) == (admin.id, image.id, request.id)
    assert (entry.draft_id, entry.side, entry.purpose) == (request.draft_id, "back", "view")


def test_linked_record_image_opens_too(client, db, uploads, make_user, marketer) -> None:
    linked = request_factory(db, marketer, status="linked")
    image = _image(db, uploads, linked)
    res = _get(client, headers_for(client, make_user("super_admin")), image.id)
    assert res.status_code == 200
    assert _log(db)[0].request_id == linked.id


@pytest.mark.parametrize("who", ["settings_admin", "marketer"])
def test_others_get_404_and_no_log(client, db, uploads, make_user, marketer, who) -> None:
    request = request_factory(db, marketer)
    image = _image(db, uploads, request)
    user = admin_with(make_user, "settings") if who == "settings_admin" else marketer
    res = _get(client, headers_for(client, user), image.id)
    assert res.status_code == 404
    assert res.json()["code"] == "image_not_found"
    assert _log(db) == []


def test_missing_file_is_404_without_the_path_in_the_log(
    client, db, uploads, make_user, marketer, caplog
) -> None:
    request = request_factory(db, marketer)
    image = _image(db, uploads, request, write=False)
    caplog.set_level(logging.INFO)

    res = _get(client, headers_for(client, make_user("super_admin")), image.id)

    assert res.status_code == 404
    assert res.json()["code"] == "image_not_found"
    assert image.file_name not in caplog.text
    assert str(uploads) not in caplog.text
    assert _log(db) == []


def test_unknown_image_is_404(client, make_user) -> None:
    res = _get(client, headers_for(client, make_user("super_admin")), uuid.uuid4())
    assert res.status_code == 404
