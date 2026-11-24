"""Legacy import preview and image fetching (specs/014 US1, FR-001–FR-003, FR-007, FR-008, FR-020;
research R6–R9; contracts/api.md). Synthetic file and generated images only."""

import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import LegacyImport, LegacyImportPreview, LegacySubscriber
from app.services import draft_service, legacy_import_service
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for

FIXTURES = Path(__file__).parent.parent / "fixtures" / "legacy"
SAMPLE = (FIXTURES / "legacy_sample.csv").read_bytes()
EXPECTED = json.loads((FIXTURES / "expected_flags.json").read_text(encoding="utf-8"))
URL = "/api/admin/imports/legacy/previews"


@pytest.fixture
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def reports_admin(make_user):
    return admin_with(make_user, "reports")


def _upload(client, user, data: bytes = SAMPLE, name: str = "legacy.csv"):
    return client.post(
        URL, files={"file": (name, data, "text/csv")}, headers=headers_for(client, user)
    )


def _ready(client, user, data: bytes = SAMPLE) -> dict:
    created = _upload(client, user, data)
    assert created.status_code == 201, created.text
    assert created.json()["status"] in ("fetching", "ready")
    got = client.get(f"{URL}/{created.json()['id']}", headers=headers_for(client, user))
    assert got.status_code == 200
    assert got.json()["status"] == "ready"
    return got.json()


def _by_index(preview: dict) -> dict[int, dict]:
    return {row["index"]: row for row in preview["flagged"]}


def _norm(flags: list[dict]) -> list[str]:
    return sorted(json.dumps(f, sort_keys=True, ensure_ascii=False) for f in flags)


# --- permissions and file problems ---


def test_main_admin_and_reports_admin_may_upload(client, make_user, uploads, reports_admin) -> None:
    assert _upload(client, make_user("super_admin")).status_code == 201
    assert _upload(client, reports_admin).status_code == 201


@pytest.mark.parametrize(
    "who",
    [
        ("admin", ["review"]),
        ("admin", ["link"]),
        ("admin", ["review", "link", "marketers"]),
        ("marketer", []),
    ],
)
def test_others_are_refused(client, make_user, uploads, who) -> None:
    role, perms = who
    user = make_user(role)
    user.permissions = perms
    response = _upload(client, user)
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_missing_columns_are_named(client, uploads, reports_admin) -> None:
    lines = SAMPLE.decode("utf-8").splitlines()
    header = lines[0].split(",")
    keep = [i for i, h in enumerate(header) if h not in ("الرقم العائلي", "ID")]
    data = "\n".join(",".join(line.split(",")[i] for i in keep) for line in lines).encode()
    response = _upload(client, reports_admin, data)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "import_columns_missing"
    assert body["columns"] == ["الرقم العائلي", "ID"]
    assert "الرقم العائلي" in body["message"]


def test_unreadable_file(client, uploads, reports_admin) -> None:
    response = _upload(client, reports_admin, b"%PDF-1.7\n\x00\xff binary", "card.pdf")
    assert response.status_code == 422
    assert response.json()["code"] == "import_file_unreadable"


# --- the preview ---


def test_preview_counts_and_flags_match_the_fixture(client, db, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    assert preview["file_name"] == "legacy.csv"
    assert preview["images_total"] == EXPECTED["images_total"]
    assert preview["images_done"] == EXPECTED["images_total"]
    counts = preview["counts"]
    assert counts["rows"] == EXPECTED["rows"]
    assert counts["ready"] == len(EXPECTED["ready"])
    assert counts["flagged"] == len(EXPECTED["flagged"])
    assert counts["waiting_choice"] == len(EXPECTED["flagged"])
    assert counts["already_imported"] == 0
    assert counts["not_counted"] == len(EXPECTED["not_counted"])
    flagged = _by_index(preview)
    assert set(flagged) == {int(i) for i in EXPECTED["flagged"]}
    for index, flags in EXPECTED["flagged"].items():
        assert _norm(flagged[int(index)]["flags"]) == _norm(flags), index
    assert flagged[6]["allowed"] == ["import", "skip", "correct"]
    assert flagged[12]["allowed"] == ["skip"]
    assert flagged[4]["allowed"] == ["import", "skip"]
    assert all(row["choice"] is None for row in preview["flagged"])
    # Flagged rows carry what the admin needs to decide.
    assert flagged[7]["phone_file"] == "0781111"
    assert flagged[7]["phone"] is None
    assert flagged[5]["family_number_file"] == "1111a00000000000o4"
    assert flagged[4]["full_name"] == "حسن تجريبي نموذج"
    assert flagged[11]["counts_in_check"] is False


def test_status_values_are_counted(client, uploads, reports_admin) -> None:
    values = {v["value"]: v for v in _ready(client, reports_admin)["status_values"]}
    assert values["تم"] == {"value": "تم", "rows": 10, "counts_in_check": True}
    assert values["ملغي"] == {"value": "ملغي", "rows": 1, "counts_in_check": False}
    assert values["مرفوض"] == {"value": "مرفوض", "rows": 1, "counts_in_check": False}
    assert values[None] == {"value": None, "rows": 1, "counts_in_check": True}


def test_nothing_is_saved_and_images_are_staged(client, db, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    assert db.scalar(select(func.count()).select_from(LegacySubscriber)) == 0
    assert db.scalar(select(func.count()).select_from(LegacyImport)) == 0
    staged = {p.name for p in uploads.iterdir()}
    # 25 links, 3 failures (not shared, not an image, not found): 22 files.
    assert len(staged) == 22
    assert staged <= draft_service.referenced_file_names(db)
    row = db.get(LegacyImportPreview, uuid.UUID(preview["id"]))
    assert row.created_by == reports_admin.id


def test_images_are_never_sent_to_the_card_reader(
    client, uploads, reports_admin, monkeypatch
) -> None:
    from app.services import card_reading_service

    def boom(*args, **kwargs):
        raise AssertionError("legacy images must never reach the card reader")

    monkeypatch.setattr(card_reading_service, "submit", boom)
    monkeypatch.setattr(card_reading_service, "run", boom)
    _ready(client, reports_admin)


def test_in_sijil_lists_live_pending_approved_and_linked_requests_only(
    client, db, make_user, uploads, reports_admin
) -> None:
    marketer = make_user("marketer")
    admin = make_user("super_admin")
    pending = request_factory(db, marketer, status="pending_review", phone="07811110002")
    linked = request_factory(db, marketer, status="linked", family_number="1111A0000000000003")
    request_factory(db, marketer, status="rejected", phone="07811110004")
    deleted = request_factory(db, marketer, status="pending_review", phone="07811110006")
    mark_deleted(db, deleted, admin)
    db.flush()
    flagged = _by_index(_ready(client, reports_admin))
    assert {"code": "in_sijil", "requests": [pending.number_label]} in flagged[2]["flags"]
    assert {"code": "in_sijil", "requests": [linked.number_label]} in flagged[3]["flags"]
    assert all(f["code"] != "in_sijil" for f in flagged.get(4, {"flags": []})["flags"])
    assert all(f["code"] != "in_sijil" for f in flagged[6]["flags"])


def _stored_legacy(db, admin, **values) -> LegacySubscriber:
    imp = LegacyImport(
        created_by=admin.id,
        file_name="old.csv",
        rows_total=1,
        imported=1,
        skipped=0,
        already_imported=0,
        not_counted=0,
        incomplete=0,
        corrected=0,
    )
    db.add(imp)
    db.flush()
    sub = LegacySubscriber(
        import_id=imp.id,
        full_name="مشترك قديم تجريبي",
        counts_in_check=True,
        incomplete=False,
        **values,
    )
    db.add(sub)
    db.flush()
    return sub


def test_against_legacy_subscribers_already_imported(
    client, db, make_user, uploads, reports_admin
) -> None:
    admin = make_user("super_admin")
    _stored_legacy(db, admin, legacy_number="T3C-001", phone="07899990001")
    _stored_legacy(db, admin, legacy_number="T3C-200", phone="07811110003")
    _stored_legacy(
        db,
        admin,
        legacy_number="T3C-201",
        family_number="1111A0000000000004",
        family_key="1111A0000000000004",
    )
    preview = _ready(client, reports_admin)
    flagged = _by_index(preview)
    assert flagged[2]["flags"] == [{"code": "already_imported"}]
    assert flagged[2]["allowed"] == []
    assert {"code": "phone_dup_legacy"} in flagged[3]["flags"]
    assert {"code": "family_dup_legacy"} in flagged[4]["flags"]
    assert preview["counts"]["already_imported"] == 1
    # An already imported row needs no choice and its images are not fetched.
    assert preview["counts"]["waiting_choice"] == preview["counts"]["flagged"]
    assert preview["images_total"] == EXPECTED["images_total"] - 2


def test_reupload_of_an_imported_file_marks_every_row(
    client, db, make_user, uploads, reports_admin
) -> None:
    admin = make_user("super_admin")
    for n in range(1, 13):
        _stored_legacy(db, admin, legacy_number=f"T3C-{n:03d}")
    preview = _ready(client, reports_admin)
    flagged = _by_index(preview)
    assert preview["counts"]["already_imported"] == 12
    # Row 12 has no valid legacy number: it is the only row that is not «مستورد سابقاً».
    assert {i for i, r in flagged.items() if r["flags"] == [{"code": "already_imported"}]} == (
        set(range(2, 15)) - {12}
    )


# --- one preview per admin, ownership, expiry, restart ---


def test_a_new_upload_replaces_the_admins_previous_preview(
    client, db, uploads, reports_admin
) -> None:
    first = _ready(client, reports_admin)
    first_files = {p.name for p in uploads.iterdir()}
    second = _ready(client, reports_admin)
    assert db.get(LegacyImportPreview, uuid.UUID(first["id"])) is None
    assert (
        client.get(f"{URL}/{first['id']}", headers=headers_for(client, reports_admin)).status_code
        == 404
    )
    assert not first_files & {p.name for p in uploads.iterdir()}
    assert db.get(LegacyImportPreview, uuid.UUID(second["id"])) is not None


def test_another_admins_preview_is_not_found(client, make_user, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    other = admin_with(make_user, "reports")
    response = client.get(f"{URL}/{preview['id']}", headers=headers_for(client, other))
    assert response.status_code == 404
    assert response.json()["code"] == "preview_not_found"
    assert (
        client.delete(f"{URL}/{preview['id']}", headers=headers_for(client, other)).status_code
        == 404
    )


def test_delete_cancels_and_removes_staged_files(client, db, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    response = client.delete(f"{URL}/{preview['id']}", headers=headers_for(client, reports_admin))
    assert response.status_code == 204
    assert db.get(LegacyImportPreview, uuid.UUID(preview["id"])) is None
    assert list(uploads.iterdir()) == []


def test_an_expired_preview_is_gone_with_its_files(
    client, db, uploads, reports_admin, frozen_clock
) -> None:
    preview = _ready(client, reports_admin)
    frozen_clock.advance(timedelta(minutes=61))
    response = client.get(f"{URL}/{preview['id']}", headers=headers_for(client, reports_admin))
    assert response.status_code == 404
    assert db.get(LegacyImportPreview, uuid.UUID(preview["id"])) is None
    assert list(uploads.iterdir()) == []


def test_previews_left_fetching_fail_at_startup(db, make_user) -> None:
    from app.core.timeutil import utc_now

    admin = make_user("super_admin")
    row = LegacyImportPreview(
        created_by=admin.id,
        expires_at=utc_now() + timedelta(hours=1),
        status="fetching",
        file_name="f.csv",
        rows=[],
    )
    db.add(row)
    db.flush()
    assert legacy_import_service.sweep_stale(db) == 1
    db.refresh(row)
    assert row.status == "failed"


def test_no_personal_value_reaches_the_logs(client, uploads, reports_admin, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    _ready(client, reports_admin)
    text = caplog.text
    for secret in (
        "07811110002",
        "1111A0000000000004",
        "سمير",
        "fake-ok-f-0002",
        "sample@example.com",
    ):
        assert secret not in text
