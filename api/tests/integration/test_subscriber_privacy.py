"""Privacy of «المشتركون» (docs/system.md v1.24 §3.1, §10 item 4, §13; specs/018 US3, FR-002,
FR-009, FR-010, FR-012, SC-004; research R7, R11). Synthetic data only.

- `link` and `reports` (without `review`) receive no national ID, family number, card field or
  image in any search row or file, from any source; the main admin and `review` do.
- A marketer reaches neither route, and their own search stays within their own requests.
- Both routes are read-only, and file logs carry `source:ref` only.
"""

import logging
from datetime import UTC, datetime

import pytest

from app.config import get_settings
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.requests import add_images, add_pin, request_factory
from tests.helpers.review import admin_with, headers_for
from tests.helpers.sas import sas_subscriber

PHONE = "07817770001"
NID = "199077700001"
FAMILY = "1990P7770000000001"
IDENTITY_KEYS = {"national_id", "family_number", "card_fields", "images"}
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def world(db, uploads, make_user):
    admin = make_user("super_admin")
    marketer = make_user("marketer")
    request = request_factory(
        db,
        marketer,
        status="approved",
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        full_name="سرية خصوصية تجريبية",
    )
    add_images(db, request, uploads)
    add_pin(db, request, admin)
    legacy = legacy_subscriber(
        db, admin, phone=PHONE, family_number=FAMILY, full_name="سرية خصوصية قديمة"
    )
    sas = sas_subscriber(
        db, admin, username=f"ZZP01-{PHONE}", phone=PHONE, full_name="سرية خصوصية SAS"
    )
    return {"request": request, "legacy": legacy, "sas": sas, "marketer": marketer}


def _get(client, user, url, **params):
    return client.get(url, params=params, headers=headers_for(client, user))


def _files(client, user, world):
    for source, obj in (
        ("sijil", world["request"]),
        ("legacy", world["legacy"]),
        ("sas", world["sas"]),
    ):
        res = _get(client, user, f"/api/admin/subscribers/{source}/{obj.id}")
        assert res.status_code == 200, res.json()
        yield source, res.json()


def _all_keys(value) -> set[str]:
    """Every key anywhere in a JSON value."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _all_keys(v)}
    return set()


def _text(value) -> str:
    return str(value)


# --- per permission (FR-009, SC-004) -------------------------------------------------------------


@pytest.mark.parametrize("permission", ["link", "reports"])
def test_no_identity_data_without_review(client, world, make_user, permission) -> None:
    user = admin_with(make_user, permission)
    rows = _get(client, user, "/api/admin/subscribers", q=PHONE).json()["items"]
    assert len(rows) == 3
    assert not _all_keys(rows) & IDENTITY_KEYS
    for source, body in _files(client, user, world):
        assert not _all_keys(body) & IDENTITY_KEYS, source
        # The values themselves are nowhere either (not under another key).
        assert NID not in _text(body) and FAMILY not in _text(body), source
        for event in body["history"]:
            assert "field" not in event  # a pin line names no field
    # Link reasons still show, without the numbers (owner Q2).
    sijil = dict(_files(client, user, world))["sijil"]
    assert {x["reason"] for x in sijil["linked"]} == {"same_phone"}


@pytest.mark.parametrize("who", ["review", "main"])
def test_review_and_main_admin_receive_identity_data(client, world, make_user, who) -> None:
    user = make_user("super_admin") if who == "main" else admin_with(make_user, "review")
    files = dict(_files(client, user, world))
    record = files["sijil"]["record"]
    assert (record["national_id"], record["family_number"]) == (NID, FAMILY)
    assert record["card_fields"] and len(record["images"]) == 2
    assert files["legacy"]["record"]["family_number"] == FAMILY
    assert any(e.get("field") == "national_id" for e in files["sijil"]["history"])
    # SAS holds no identity document at all.
    assert not set(files["sas"]["record"]) & IDENTITY_KEYS


def test_search_rows_never_carry_identity_data_even_for_review(client, world, make_user) -> None:
    rows = _get(client, admin_with(make_user, "review"), "/api/admin/subscribers", q=NID).json()
    assert not _all_keys(rows) & IDENTITY_KEYS
    assert NID not in _text(rows["items"])


@pytest.mark.parametrize("permission", ["link", "reports"])
def test_no_image_for_link_or_reports(client, db, world, make_user, permission) -> None:
    from sqlalchemy import select

    from app.models import RequestImage

    image_id = db.scalar(
        select(RequestImage.id).where(RequestImage.request_id == world["request"].id)
    )
    res = _get(client, admin_with(make_user, permission), f"/api/admin/request-images/{image_id}")
    assert res.status_code == 404


# --- the marketer (FR-002, US3) ------------------------------------------------------------------


def test_marketer_reaches_neither_route(client, world) -> None:
    marketer = world["marketer"]
    assert _get(client, marketer, "/api/admin/subscribers", q=PHONE).status_code == 403
    res = _get(client, marketer, f"/api/admin/subscribers/sijil/{world['request'].id}")
    assert res.status_code == 403


def test_marketer_own_search_stays_own(client, db, world, make_user) -> None:
    """A phone of a SAS row and of another marketer's request finds nothing for this marketer."""
    other = make_user("marketer")
    res = _get(client, other, "/api/requests", q=PHONE)
    assert res.status_code == 200
    assert res.json()["items"] == []
    res = _get(client, other, "/api/requests", q="سرية خصوصية")
    assert res.json()["items"] == []


# --- read-only and logs (FR-010, FR-012) ---------------------------------------------------------


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_read_only(client, world, make_user, method) -> None:
    headers = headers_for(client, make_user("super_admin"))
    for url in ("/api/admin/subscribers", f"/api/admin/subscribers/sijil/{world['request'].id}"):
        assert client.request(method, url, headers=headers).status_code == 405, (method, url)


def test_file_logs_carry_the_reference_only(client, world, make_user, caplog) -> None:
    user = admin_with(make_user, "review")
    with caplog.at_level(logging.INFO, logger="sijil.subscribers"):
        list(_files(client, user, world))
    text = caplog.text
    assert f"sijil:{world['request'].id}" in text
    for value in (PHONE, NID, FAMILY, "سرية", world["request"].username):
        assert value not in text
