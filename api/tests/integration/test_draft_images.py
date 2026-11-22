"""US2 — card images: upload, checks, replace, private serving and the access log
(specs/005 research.md R6, R7). Images are synthetic rectangles generated with Pillow."""

import io
import uuid
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import get_settings
from app.models import Draft, DraftImage, ImageAccessLog
from tests.conftest import auth_header, login


def synthetic_jpeg(width: int = 1600, height: int = 1000, fmt: str = "JPEG") -> bytes:
    image = Image.new("RGB", (width, height), (40, 90, 160))
    ImageDraw.Draw(image).rectangle((20, 20, width - 20, height - 20), outline=(255, 255, 255))
    buf = io.BytesIO()
    image.save(buf, format=fmt, quality=80)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _h(response, client_id: str | None = None) -> dict[str, str]:
    headers = auth_header(response)
    headers["X-Client-Id"] = client_id or str(uuid.uuid4())
    return headers


@pytest.fixture
def owner(client, make_user):
    user = make_user("marketer")
    return user, _h(login(client, user.phone))


@pytest.fixture
def draft_id(client, owner) -> str:
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=owner[1])
    assert res.status_code == 201
    return draft_id


def upload(client, draft_id, side, headers, data=None, content_type="image/jpeg"):
    payload = data if data is not None else synthetic_jpeg()
    return client.post(
        f"/api/drafts/{draft_id}/images/{side}",
        files={"file": ("photo.jpg", payload, content_type)},
        headers=headers,
    )


def files_in(path: Path) -> list[str]:
    return sorted(p.name for p in path.iterdir() if p.is_file())


# --- upload ----------------------------------------------------------------------------------


def test_upload_stores_private_file_and_bumps_version(client, db, owner, draft_id, uploads):
    res = upload(client, draft_id, "front", owner[1], synthetic_jpeg(1600, 1000))
    assert res.status_code == 200
    body = res.json()
    assert body["version"] == 2
    front = body["images"]["front"]
    assert front["width"] == 1600 and front["height"] == 1000
    assert body["images"]["back"] is None
    assert [m["field"] for m in body["missing"]][:1] == ["image_back"]

    row = db.scalars(select(DraftImage).where(DraftImage.draft_id == uuid.UUID(draft_id))).one()
    assert row.side == "front"
    assert row.uploaded_by == owner[0].id
    assert row.size_bytes == (uploads / row.file_name).stat().st_size
    assert row.file_name.endswith(".jpg") and len(row.file_name) == 36  # <uuid hex>.jpg
    assert files_in(uploads) == [row.file_name]
    # The stored name is never the uploaded one.
    assert "photo" not in row.file_name


def test_back_can_be_uploaded_before_front(client, owner, draft_id):
    res = upload(client, draft_id, "back", owner[1])
    assert res.status_code == 200
    assert res.json()["images"]["back"] is not None
    assert res.json()["images"]["front"] is None


def test_upload_from_same_page_then_patch_is_same_client(client, owner, draft_id):
    """An upload finishing while typing gives a same_client 409 (silent rebase in the UI)."""
    upload(client, draft_id, "front", owner[1])
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"address": "حي"}},
        headers=owner[1],
    )
    assert res.status_code == 409
    assert res.json()["same_client"] is True
    assert res.json()["version"] == 2


def test_upload_needs_client_id(client, owner, draft_id):
    headers = {"Authorization": owner[1]["Authorization"]}
    assert upload(client, draft_id, "front", headers).status_code == 422


def test_invalid_side_is_rejected(client, owner, draft_id):
    assert upload(client, draft_id, "left", owner[1]).status_code == 422


# --- refusals --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(synthetic_jpeg(fmt="PNG"), id="png"),
        pytest.param("ليست صورة".encode(), id="text"),
        pytest.param(b"\xff\xd8\xff" + b"\x00" * 100, id="jpeg magic but broken"),
        pytest.param(b"", id="empty"),
    ],
)
def test_non_jpeg_is_invalid_image(client, owner, draft_id, uploads, data):
    res = upload(client, draft_id, "front", owner[1], data)
    assert res.status_code == 422
    assert res.json()["code"] == "invalid_image"
    assert files_in(uploads) == []


def test_too_large_is_413(client, owner, draft_id, uploads, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_image_bytes", 10_000)
    res = upload(client, draft_id, "front", owner[1], synthetic_jpeg(1600, 1600))
    assert len(synthetic_jpeg(1600, 1600)) > 10_000
    assert res.status_code == 413
    assert res.json()["code"] == "image_too_large"
    assert files_in(uploads) == []


def test_too_big_dimensions_is_422(client, owner, draft_id, uploads):
    res = upload(client, draft_id, "front", owner[1], synthetic_jpeg(2000, 1000))
    assert res.status_code == 422
    assert res.json()["code"] == "image_too_big_dimensions"
    assert files_in(uploads) == []


# --- replace ---------------------------------------------------------------------------------


def test_replace_keeps_one_row_and_removes_old_file(client, db, owner, draft_id, uploads):
    first = upload(client, draft_id, "front", owner[1]).json()["images"]["front"]
    old_name = db.get(DraftImage, uuid.UUID(first["id"])).file_name
    second = upload(client, draft_id, "front", owner[1], synthetic_jpeg(1200, 800)).json()
    rows = db.scalars(select(DraftImage).where(DraftImage.draft_id == uuid.UUID(draft_id))).all()
    assert len(rows) == 1
    assert rows[0].width == 1200
    assert second["version"] == 3
    assert old_name not in files_in(uploads)
    assert files_in(uploads) == [rows[0].file_name]


# --- access ----------------------------------------------------------------------------------


def _image_id(client, owner, draft_id) -> str:
    return upload(client, draft_id, "front", owner[1]).json()["images"]["front"]["id"]


def test_other_marketer_gets_404_and_cannot_upload(client, make_user, owner, draft_id):
    image_id = _image_id(client, owner, draft_id)
    other = _h(login(client, make_user("marketer").phone))
    assert client.get(f"/api/draft-images/{image_id}", headers=other).status_code == 404
    assert upload(client, draft_id, "back", other).status_code == 404


def test_admin_without_review_gets_404(client, make_user, owner, draft_id):
    image_id = _image_id(client, owner, draft_id)
    admin = make_user("admin")
    admin.permissions = ["settings", "link"]
    h = auth_header(login(client, admin.phone))
    assert client.get(f"/api/draft-images/{image_id}", headers=h).status_code == 404


def test_anonymous_gets_401(client, owner, draft_id):
    image_id = _image_id(client, owner, draft_id)
    assert client.get(f"/api/draft-images/{image_id}").status_code == 401


def test_unknown_image_is_404(client, owner):
    res = client.get(f"/api/draft-images/{uuid.uuid4()}", headers=owner[1])
    assert res.status_code == 404
    assert res.json()["code"] == "image_not_found"


@pytest.mark.parametrize("who", ["owner", "super_admin", "review_admin"])
def test_allowed_viewers_get_the_jpeg_and_each_open_is_logged(
    client, db, make_user, owner, draft_id, who
):
    image_id = _image_id(client, owner, draft_id)
    if who == "owner":
        viewer, h = owner[0], owner[1]
    elif who == "super_admin":
        viewer = make_user("super_admin")
        h = auth_header(login(client, viewer.phone))
    else:
        viewer = make_user("admin")
        viewer.permissions = ["review"]
        h = auth_header(login(client, viewer.phone))

    for _ in range(2):
        res = client.get(f"/api/draft-images/{image_id}", headers=h)
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"
        assert res.headers["cache-control"] == "private, no-store"
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.content[:3] == b"\xff\xd8\xff"

    rows = db.scalars(
        select(ImageAccessLog).where(ImageAccessLog.image_id == uuid.UUID(image_id))
    ).all()
    assert len(rows) == 2
    assert {r.user_id for r in rows} == {viewer.id}
    assert {r.draft_id for r in rows} == {uuid.UUID(draft_id)}
    assert {r.side for r in rows} == {"front"}


def test_refused_access_is_not_logged(client, db, make_user, owner, draft_id):
    image_id = _image_id(client, owner, draft_id)
    other = _h(login(client, make_user("marketer").phone))
    client.get(f"/api/draft-images/{image_id}", headers=other)
    assert db.scalars(select(ImageAccessLog)).all() == []


# --- privacy ---------------------------------------------------------------------------------


def test_file_is_not_reachable_by_name(client, db, owner, draft_id):
    upload(client, draft_id, "front", owner[1])
    name = db.scalars(select(DraftImage.file_name)).one()
    for path in (f"/api/{name}", f"/api/uploads/{name}", f"/{name}", f"/uploads/{name}"):
        res = client.get(path, headers=owner[1])
        assert res.status_code == 404, path
        assert res.content[:3] != b"\xff\xd8\xff"


def test_draft_row_version_matches_response(client, db, owner, draft_id):
    body = upload(client, draft_id, "front", owner[1]).json()
    db.expire_all()
    assert db.get(Draft, uuid.UUID(draft_id)).version == body["version"]
