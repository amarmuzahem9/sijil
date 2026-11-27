"""Privacy of «التقارير والتصدير» (docs/system.md v1.25 §3.1, §10 item 4, §11; specs/019 FR-001,
FR-002, FR-009, FR-016, SC-003; research R1, R12). Synthetic data only.

- The report is open to the main admin and `reports`; every other caller gets 403, marketers too.
- No national ID, family number, card field, image, amount, rate or payment key, whoever asks.
- `can_export_identity` is true only for the main admin and `reports` + `review`.
"""

from datetime import UTC, datetime

import pytest

from app.core.timeutil import BAGHDAD
from tests.helpers.requests import add_images, request_factory
from tests.helpers.review import admin_with, headers_for

REPORT = "/api/admin/reports/requests"
OPTIONS = "/api/admin/reports/options"
NOVEMBER = {"period": "range", "from": "2026-11-01", "to": "2026-11-30"}
FORBIDDEN_FRAGMENTS = (
    "national",
    "family",
    "card",
    "birth",
    "issue",
    "expiry",
    "image",
    "phone",
    "username",
    "address",
    "landmark",
    "location",
    "amount",
    "rate",
    "paid",
    "price",
)


@pytest.fixture
def world(db, make_user, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    marketer = make_user("marketer")
    at = datetime(2026, 11, 10, 12, tzinfo=BAGHDAD).astimezone(UTC)
    request = request_factory(
        db,
        marketer,
        status="linked",
        submitted_at=at,
        otp_verified_at=at,
        approved_at=at,
        linked_at=at,
    )
    add_images(db, request, tmp_path)
    return {"marketer": marketer, "request": request}


def _keys(value, out: set[str]) -> set[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            out.add(key)
            _keys(item, out)
    elif isinstance(value, list):
        for item in value:
            _keys(item, out)
    return out


@pytest.mark.parametrize(
    ("who", "status", "identity"),
    [
        ("super_admin", 200, True),
        ("reports", 200, False),
        ("reports+review", 200, True),
        ("review", 403, None),
        ("commissions", 403, None),
        ("link+settings+marketers+delete", 403, None),
        ("marketer", 403, None),
    ],
)
def test_who_may_open_the_report(client, make_user, world, who, status, identity) -> None:
    if who == "super_admin":
        user = make_user("super_admin")
    elif who == "marketer":
        user = world["marketer"]
    else:
        user = admin_with(make_user, *who.split("+"))
    h = headers_for(client, user)
    report = client.get(REPORT, params=NOVEMBER, headers=h)
    options = client.get(OPTIONS, headers=h)
    assert report.status_code == status
    assert options.status_code == status
    if status == 200:
        assert report.json()["can_export_identity"] is identity
    else:
        assert report.json()["code"] == "forbidden"


@pytest.mark.parametrize("who", ["super_admin", "reports", "reports+review"])
def test_no_identity_or_money_key_whoever_asks(client, make_user, world, who) -> None:
    user = (
        make_user("super_admin") if who == "super_admin" else admin_with(make_user, *who.split("+"))
    )
    body = client.get(REPORT, params=NOVEMBER, headers=headers_for(client, user)).json()
    assert world["request"].number in [r["number"] for r in body["rows"]]
    keys = _keys(body, set())
    leaked = {k for k in keys if any(f in k.lower() for f in FORBIDDEN_FRAGMENTS)}
    assert leaked == set()
    text = str(body)
    request = world["request"]
    for value in (request.national_id, request.family_number, request.phone, request.username):
        assert value not in text


# --- the marketer and every export route (specs/019 US4, FR-014; T039) ---------------------------

EXPORTS = "/api/admin/exports"


@pytest.fixture
def inline_exports(db, monkeypatch, exports_dir):
    from app.services import export_service

    monkeypatch.setattr(
        export_service, "submit", lambda export_id: export_service.run(export_id, session=db)
    )


@pytest.fixture
def admin_export(client, make_user, world, inline_exports):
    """A ready export of the main admin, to aim the marketer's calls at a real id."""
    boss = make_user("super_admin")
    h = headers_for(client, boss)
    created = client.post(EXPORTS, json=NOVEMBER, headers=h)
    assert created.status_code == 202
    return {"id": created.json()["id"], "headers": h}


def test_a_marketer_is_refused_on_every_report_and_export_route(
    client, world, admin_export
) -> None:
    h = headers_for(client, world["marketer"])
    export_id = admin_export["id"]
    calls = [
        ("get", REPORT, {"params": NOVEMBER}),
        ("get", OPTIONS, {}),
        ("post", EXPORTS, {"json": NOVEMBER}),
        ("post", EXPORTS, {"json": {**NOVEMBER, "include_identity": True}}),
        ("get", EXPORTS, {}),
        ("get", f"{EXPORTS}/{export_id}", {}),
        ("post", f"{EXPORTS}/{export_id}/ticket", {}),
        ("get", "/api/admin/commissions/export", {"params": {"month": "2026-11"}}),
    ]
    for method, url, kwargs in calls:
        response = getattr(client, method)(url, headers=h, **kwargs)
        assert response.status_code == 403, (method, url, response.status_code)
        assert response.json()["code"] == "forbidden", (method, url)


def test_the_ticket_alone_decides_the_download(client, world, admin_export) -> None:
    """A download link opened while signed in as a marketer still serves only that ticket's
    export, and only once: the session adds nothing (research R7)."""
    ticket = client.post(f"{EXPORTS}/{admin_export['id']}/ticket", headers=admin_export["headers"])
    url = ticket.json()["url"]
    marketer = headers_for(client, world["marketer"])
    first = client.get(url, headers=marketer)
    assert first.status_code == 200
    assert first.headers["content-type"] == "application/zip"
    again = client.get(url, headers=marketer)
    assert again.status_code == 403 and again.json()["code"] == "ticket_invalid"
    # Without a ticket, a session — even the requester's — opens nothing.
    bare = client.get(f"{EXPORTS}/{admin_export['id']}/download", headers=admin_export["headers"])
    assert bare.status_code == 403 and bare.json()["code"] == "ticket_invalid"


# --- a sheet without the box never has an identity column (FR-008, SC-003; T040) ----------------


@pytest.mark.parametrize("who", ["super_admin", "reports+review", "reports"])
def test_no_identity_header_without_the_box(client, make_user, world, inline_exports, who) -> None:
    import io
    import zipfile

    from openpyxl import load_workbook

    from app.services.export_sheet import IDENTITY_HEADERS

    user = (
        make_user("super_admin") if who == "super_admin" else admin_with(make_user, *who.split("+"))
    )
    h = headers_for(client, user)
    created = client.post(EXPORTS, json=NOVEMBER, headers=h)
    assert created.status_code == 202 and created.json()["include_identity"] is False
    url = client.post(f"{EXPORTS}/{created.json()['id']}/ticket", headers=h).json()["url"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(url).content))
    assert archive.namelist() == ["requests.xlsx"]
    ws = load_workbook(io.BytesIO(archive.read("requests.xlsx"))).active
    headers = {c.value for c in ws[1]}
    assert not headers & set(IDENTITY_HEADERS)
    text = str(list(ws.iter_rows(values_only=True)))
    request = world["request"]
    for value in (request.national_id, request.family_number, request.issuing_authority):
        assert value not in text
