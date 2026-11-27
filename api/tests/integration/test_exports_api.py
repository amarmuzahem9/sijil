"""The requests export of «التقارير والتصدير» (docs/system.md v1.25 §11, §13; specs/019 US2,
FR-007 to FR-013; research R5–R8; contracts/api.md; analysis C1, M1). Synthetic data only.
"""

import io
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.config import get_settings
from app.core.timeutil import BAGHDAD
from app.models import AuditLog, Export, ImageAccessLog
from app.services import export_service, export_sheet
from tests.helpers.requests import add_images, mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for

EXPORTS = "/api/admin/exports"
NOVEMBER = {"period": "range", "from": "2026-11-01", "to": "2026-11-30"}


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    directory = tmp_path / "uploads"
    directory.mkdir()
    monkeypatch.setattr(get_settings(), "uploads_dir", str(directory))
    return directory


@pytest.fixture(autouse=True)
def inline_jobs(db, monkeypatch, exports_dir):
    """The build runs at once on the test session instead of a worker thread (research R5)."""
    monkeypatch.setattr(
        export_service, "submit", lambda export_id: export_service.run(export_id, session=db)
    )


@pytest.fixture
def paused_jobs(monkeypatch):
    """The build never starts: the export stays `preparing`."""
    monkeypatch.setattr(export_service, "submit", lambda export_id: None)


def _at(day: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, 10, minute, tzinfo=BAGHDAD).astimezone(UTC)


@pytest.fixture
def world(db, make_user, uploads):
    from app.models import Area, Plan, Tower

    area = Area(name="منطقة تصدير")
    db.add(area)
    db.flush()
    tower = Tower(code="EXP01", name="برج تصدير", area_id=area.id)
    plan = Plan(name="فئة تصدير", trial_price=20000, second_price=35000)
    db.add_all([tower, plan])
    db.flush()
    marketer = make_user("marketer")
    place = {"area": area, "tower": tower, "plan": plan}
    requests = []
    for i in range(3):
        r = request_factory(
            db,
            marketer,
            **place,
            submitted_at=_at(5, i),
            otp_verified_at=_at(5, i),
            approved_at=_at(5, i),
        )
        add_images(db, r, uploads)
        requests.append(r)
    return {"marketer": marketer, "requests": requests, "tower": tower, "place": place}


def _body(world, **over):
    return {**NOVEMBER, "tower_id": world["tower"].id, **over}


def _create(client, h, world, **over):
    return client.post(EXPORTS, json=_body(world, **over), headers=h)


def _ticket(client, h, export_id):
    return client.post(f"{EXPORTS}/{export_id}/ticket", headers=h)


def _download(client, url):
    return client.get(url)  # no bearer: the ticket alone (research R7)


def _zip(response) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(response.content))


def _audit(db, action: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)))


@pytest.fixture
def boss(make_user):
    return make_user("super_admin")


@pytest.fixture
def h(client, boss):
    return headers_for(client, boss)


def test_lifecycle_with_identity(db, client, h, boss, world, uploads) -> None:
    created = _create(client, h, world, include_identity=True)
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["include_identity"] is True
    export_id = body["id"]
    got = client.get(f"{EXPORTS}/{export_id}", headers=h).json()
    assert got["state"] == "ready"
    assert got["row_count"] == 3 and got["missing_images"] == 0
    assert got["expires_at"] is not None and got["error"] is None

    ticket = _ticket(client, h, export_id)
    assert ticket.status_code == 200
    assert ticket.json()["expires_in"] == 60
    response = _download(client, ticket.json()["url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    archive = _zip(response)
    numbers = sorted(r.number for r in world["requests"])
    expected = {"requests.xlsx"} | {
        f"cards/T3C-{n}-{side}.jpg" for n in numbers for side in ("front", "back")
    }
    assert set(archive.namelist()) == expected
    for n in numbers:
        assert archive.read(f"cards/T3C-{n}-front.jpg")[:2] == b"\xff\xd8"  # a JPEG
    ws = load_workbook(io.BytesIO(archive.read("requests.xlsx"))).active
    headers = [c.value for c in ws[1]]
    assert "الرقم الوطني" in headers and "صورة الوجه" in headers
    # newest first, as in the report
    assert [ws.cell(row=i, column=1).value for i in (2, 3, 4)] == [
        f"T3C-{n}" for n in reversed(numbers)
    ]
    link = ws.cell(row=2, column=headers.index("صورة الوجه") + 1).hyperlink
    assert link.target == f"cards/T3C-{numbers[-1]}-front.jpg"

    # audit: one export entry with the numbers, one download entry (FR-011)
    [exported] = _audit(db, "requests.exported")
    assert exported.actor_id == boss.id and exported.entity_id == export_id
    assert exported.after["row_count"] == 3
    assert sorted(exported.after["numbers"]) == numbers
    assert exported.after["identity"] is True and exported.after["missing_images"] == 0
    assert exported.after["filters"]["tower_id"] == world["tower"].id
    [downloaded] = _audit(db, "export.downloaded")
    assert downloaded.actor_id == boss.id and downloaded.after["images"] == 6
    # every image sent is in the image access log (analysis C1)
    access = list(db.scalars(select(ImageAccessLog).where(ImageAccessLog.purpose == "export")))
    assert len(access) == 6
    sent = {(a.request_id, a.side) for a in access}
    assert sent == {(r.id, side) for r in world["requests"] for side in ("front", "back")}
    assert all(a.user_id == boss.id for a in access)
    image_ids = {i.id for r in world["requests"] for i in r.images}
    assert {a.image_id for a in access} == image_ids


def test_no_audit_row_holds_personal_data(db, client, h, world) -> None:
    export_id = _create(client, h, world, include_identity=True).json()["id"]
    _download(client, _ticket(client, h, export_id).json()["url"])
    text = " ".join(
        str((a.before, a.after))
        for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "export"))
    )
    for r in world["requests"]:
        for value in (r.full_name, r.phone, r.national_id, r.family_number, r.username):
            assert value not in text


def test_without_the_box_there_is_no_identity_and_no_cards(db, client, h, world) -> None:
    export_id = _create(client, h, world).json()["id"]
    response = _download(client, _ticket(client, h, export_id).json()["url"])
    archive = _zip(response)
    assert archive.namelist() == ["requests.xlsx"]
    ws = load_workbook(io.BytesIO(archive.read("requests.xlsx"))).active
    headers = [c.value for c in ws[1]]
    assert not set(headers) & set(export_sheet.IDENTITY_HEADERS)
    assert db.scalars(select(ImageAccessLog).where(ImageAccessLog.purpose == "export")).all() == []
    [downloaded] = _audit(db, "export.downloaded")
    assert downloaded.after["images"] == 0


@pytest.mark.parametrize("who", ["reports", "reports+link"])
def test_identity_needs_review(client, make_user, world, who) -> None:
    user = admin_with(make_user, *who.split("+"))
    h = headers_for(client, user)
    response = _create(client, h, world, include_identity=True)
    assert response.status_code == 403
    assert response.json()["code"] == "identity_export_forbidden"
    # the same admin may export without identity data
    assert _create(client, h, world).status_code == 202


def test_reports_and_review_may_export_identity(client, make_user, world) -> None:
    user = admin_with(make_user, "reports", "review")
    response = _create(client, headers_for(client, user), world, include_identity=True)
    assert response.status_code == 202


def test_no_rows(client, h, world) -> None:
    response = _create(client, h, world, status="rejected")
    assert response.status_code == 422
    assert response.json()["code"] == "no_rows"


def test_too_large(client, h, world, monkeypatch) -> None:
    assert export_service.MAX_ROWS == 5000
    monkeypatch.setattr(export_service, "MAX_ROWS", 2)
    response = _create(client, h, world)
    assert response.status_code == 422
    assert response.json()["code"] == "export_too_large"


def test_one_export_in_progress(client, h, world, paused_jobs) -> None:
    first = _create(client, h, world)
    assert first.status_code == 202 and first.json()["state"] == "preparing"
    second = _create(client, h, world)
    assert second.status_code == 409
    assert second.json()["code"] == "export_in_progress"
    ticket = _ticket(client, h, first.json()["id"])
    assert ticket.status_code == 409 and ticket.json()["code"] == "export_not_ready"


def test_period_invalid(client, h, world) -> None:
    response = client.post(
        EXPORTS, json={"period": "range", "from": "2026-11-02", "to": "2026-11-01"}, headers=h
    )
    assert response.status_code == 422 and response.json()["code"] == "period_invalid"


def test_own_exports_only(client, h, make_user, world) -> None:
    export_id = _create(client, h, world).json()["id"]
    other = headers_for(client, make_user("super_admin"))
    assert client.get(f"{EXPORTS}/{export_id}", headers=other).status_code == 404
    assert _ticket(client, other, export_id).status_code == 404
    assert client.get(EXPORTS, headers=other).json()["items"] == []
    mine = client.get(EXPORTS, headers=h).json()["items"]
    assert [e["id"] for e in mine] == [export_id]
    assert client.get(f"{EXPORTS}/{uuid.uuid4()}", headers=h).status_code == 404


def test_a_ticket_works_once(client, h, world) -> None:
    export_id = _create(client, h, world).json()["id"]
    url = _ticket(client, h, export_id).json()["url"]
    assert _download(client, url).status_code == 200
    again = _download(client, url)
    assert again.status_code == 403 and again.json()["code"] == "ticket_invalid"
    # a new ticket works again within the 24 hours
    assert _download(client, _ticket(client, h, export_id).json()["url"]).status_code == 200


def test_a_ticket_expires_after_a_minute(client, h, world, frozen_clock) -> None:
    export_id = _create(client, h, world).json()["id"]
    url = _ticket(client, h, export_id).json()["url"]
    frozen_clock.advance(timedelta(seconds=61))
    response = _download(client, url)
    assert response.status_code == 403 and response.json()["code"] == "ticket_invalid"


def test_a_ticket_opens_only_its_own_export(db, client, h, world) -> None:
    first = _create(client, h, world).json()["id"]
    second = _create(client, h, world).json()["id"]
    url = _ticket(client, h, first).json()["url"]
    forged = url.replace(first, second)
    response = _download(client, forged)
    assert response.status_code == 403 and response.json()["code"] == "ticket_invalid"
    bad = f"{EXPORTS}/{first}/download?ticket=not-a-ticket"
    assert _download(client, bad).status_code == 403


def test_review_lost_before_the_ticket_removes_the_file(
    db, client, make_user, world, exports_dir
) -> None:
    user = admin_with(make_user, "reports", "review")
    h = headers_for(client, user)
    export_id = _create(client, h, world, include_identity=True).json()["id"]
    assert (exports_dir / export_id).is_dir()
    user.permissions = ["reports"]
    db.flush()
    response = _ticket(client, h, export_id)
    assert response.status_code == 403 and response.json()["code"] == "identity_export_forbidden"
    assert db.get(Export, uuid.UUID(export_id)).state == "removed"
    assert not (exports_dir / export_id).exists()


def test_review_lost_before_the_download_removes_the_file(
    db, client, make_user, world, exports_dir
) -> None:
    user = admin_with(make_user, "reports", "review")
    h = headers_for(client, user)
    export_id = _create(client, h, world, include_identity=True).json()["id"]
    url = _ticket(client, h, export_id).json()["url"]
    user.permissions = ["reports"]
    db.flush()
    response = _download(client, url)
    assert response.status_code == 403
    assert db.get(Export, uuid.UUID(export_id)).state == "removed"
    assert not (exports_dir / export_id).exists()
    assert db.scalars(select(ImageAccessLog).where(ImageAccessLog.purpose == "export")).all() == []


def test_reports_lost_before_the_download(db, client, make_user, world) -> None:
    user = admin_with(make_user, "reports")
    h = headers_for(client, user)
    export_id = _create(client, h, world).json()["id"]
    url = _ticket(client, h, export_id).json()["url"]
    user.permissions = ["review"]
    db.flush()
    assert _download(client, url).status_code == 403


def test_an_image_erased_after_the_build_is_not_sent(db, client, h, boss, world, uploads) -> None:
    export_id = _create(client, h, world, include_identity=True).json()["id"]
    gone = world["requests"][0]
    gone.status = "rejected"
    gone.approved_at = None
    gone.rejected_at = _at(6)
    gone.rejected_by = boss.id
    gone.rejection_reason = "card_unclear"
    db.flush()
    for image in gone.images:
        (uploads / image.file_name).unlink()
    mark_deleted(db, gone, boss)
    archive = _zip(_download(client, _ticket(client, h, export_id).json()["url"]))
    assert not [n for n in archive.namelist() if n.startswith(f"cards/T3C-{gone.number}-")]
    assert len([n for n in archive.namelist() if n.startswith("cards/")]) == 4
    access = db.scalars(select(ImageAccessLog).where(ImageAccessLog.purpose == "export")).all()
    assert len(access) == 4 and gone.id not in {a.request_id for a in access}
    assert _audit(db, "export.downloaded")[0].after["images"] == 4


def test_a_missing_image_is_counted_at_build(db, client, h, world, uploads) -> None:
    (uploads / world["requests"][1].images[0].file_name).unlink()
    export_id = _create(client, h, world, include_identity=True).json()["id"]
    got = client.get(f"{EXPORTS}/{export_id}", headers=h).json()
    assert got["state"] == "ready" and got["missing_images"] == 1
    assert _audit(db, "requests.exported")[0].after["missing_images"] == 1


def test_a_failed_build_writes_no_audit_entry(db, client, h, world, exports_dir, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(export_sheet, "request_workbook", broken)
    export_id = _create(client, h, world).json()["id"]
    got = client.get(f"{EXPORTS}/{export_id}", headers=h).json()
    assert got["state"] == "failed" and got["error"] == "build_failed"
    assert _audit(db, "requests.exported") == []
    assert not (exports_dir / export_id).exists()


def test_the_job_checks_the_permissions_again(db, client, make_user, world, paused_jobs):
    user = admin_with(make_user, "reports", "review")
    h = headers_for(client, user)
    export_id = _create(client, h, world, include_identity=True).json()["id"]
    user.permissions = ["reports"]
    db.flush()
    export_service.run(uuid.UUID(export_id), session=db)
    export = db.get(Export, uuid.UUID(export_id))
    assert export.state == "failed" and export.error_code == "permission_lost"
    assert _audit(db, "requests.exported") == []


def test_sweep_at_startup_fails_a_left_preparing_export(db, client, h, world, paused_jobs):
    export_id = _create(client, h, world).json()["id"]
    export_service.sweep_at_startup(session=db)
    export = db.get(Export, uuid.UUID(export_id))
    assert export.state == "failed" and export.error_code == "interrupted"


def test_a_marketer_cannot_export(client, world) -> None:
    h = headers_for(client, world["marketer"])
    assert _create(client, h, world).status_code == 403
    assert client.get(EXPORTS, headers=h).status_code == 403
