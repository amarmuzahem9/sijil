"""Legacy import choices and confirmation (specs/014 US1: FR-004–FR-006, FR-005a, FR-009, FR-010,
FR-020, SC-001, SC-006; research R6, R10, R11; contracts/api.md). Synthetic data only."""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import AuditLog, LegacyImage, LegacyImport, LegacyImportPreview, LegacySubscriber
from app.services import audit_service
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for
from tests.integration.test_legacy_preview import URL, _ready

# Row → choice for the sample file (expected_flags.json): one of the two T3C-012 rows, and
# the row without a legacy number, are skipped; row 6 gets a corrected family number.
CORRECTED = "1111A0000000000006"
CHOICES = [
    {"index": 4, "choice": "import"},
    {"index": 5, "choice": "import"},
    {"index": 6, "choice": "correct", "family_number": CORRECTED},
    {"index": 7, "choice": "import"},
    {"index": 8, "choice": "import"},
    {"index": 9, "choice": "import"},
    {"index": 11, "choice": "import"},
    {"index": 12, "choice": "skip"},
    {"index": 13, "choice": "import"},
    {"index": 14, "choice": "skip"},
]


@pytest.fixture
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def reports_admin(make_user):
    return admin_with(make_user, "reports")


def _put(client, user, preview_id, choices):
    return client.put(
        f"{URL}/{preview_id}/choices", json={"choices": choices}, headers=headers_for(client, user)
    )


def _confirm(client, user, preview_id):
    return client.post(f"{URL}/{preview_id}/confirm", headers=headers_for(client, user))


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _row(preview: dict, index: int) -> dict:
    return next(r for r in preview["flagged"] if r["index"] == index)


# --- choices ---


def test_choices_are_saved_partially(client, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    response = _put(client, reports_admin, preview["id"], CHOICES[:2])
    assert response.status_code == 200
    body = response.json()
    assert _row(body, 4)["choice"] == "import"
    assert _row(body, 7)["choice"] is None
    assert body["counts"]["waiting_choice"] == len(CHOICES) - 2


@pytest.mark.parametrize(
    "choice",
    [
        {"index": 12, "choice": "import"},  # no legacy number: skip only
        {"index": 4, "choice": "correct", "family_number": CORRECTED},  # not a length flag
        {"index": 2, "choice": "skip"},  # a ready row needs no choice
        {"index": 99, "choice": "skip"},  # no such row
    ],
)
def test_choices_not_allowed(client, uploads, reports_admin, choice) -> None:
    preview = _ready(client, reports_admin)
    response = _put(client, reports_admin, preview["id"], [choice])
    assert response.status_code == 422
    assert response.json()["code"] == "choice_not_allowed"


def test_a_repeated_legacy_number_can_be_imported_once(client, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    assert (
        _put(client, reports_admin, preview["id"], [{"index": 13, "choice": "import"}]).status_code
        == 200
    )
    response = _put(client, reports_admin, preview["id"], [{"index": 14, "choice": "import"}])
    assert response.status_code == 422
    assert response.json()["code"] == "choice_not_allowed"


def test_a_correction_is_rechecked(client, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    # Corrected to row 4's family number: now a repeat in the file.
    body = _put(
        client,
        reports_admin,
        preview["id"],
        [{"index": 6, "choice": "correct", "family_number": "1111A0000000000004"}],
    ).json()
    row6 = _row(body, 6)
    assert row6["choice"] == "correct"
    assert row6["corrected_family_number"] == "1111A0000000000004"
    assert {"code": "family_dup_file", "rows": [4, 5]} in row6["flags"]
    assert {"code": "family_dup_file", "rows": [5, 6]} in _row(body, 4)["flags"]
    # A correction must give an 18-character family number.
    bad = _put(
        client,
        reports_admin,
        preview["id"],
        [{"index": 6, "choice": "correct", "family_number": "1111A00"}],
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "invalid_family_number"
    # Back to «استيراد»: the correction is dropped and the repeat disappears.
    body = _put(client, reports_admin, preview["id"], [{"index": 6, "choice": "import"}]).json()
    assert _row(body, 6)["corrected_family_number"] is None
    assert all(f["code"] != "family_dup_file" or f["rows"] == [5] for f in _row(body, 4)["flags"])


def test_skip_all_for_a_group_then_change_one_row(client, uploads, reports_admin) -> None:
    """«تخطي للكل» is a PUT of skip for the group's rows; any row can be changed after (FR-005a)."""
    preview = _ready(client, reports_admin)
    group = [4, 5]  # «رقم عائلي مكرر في الملف»
    body = _put(
        client, reports_admin, preview["id"], [{"index": i, "choice": "skip"} for i in group]
    ).json()
    assert [_row(body, i)["choice"] for i in group] == ["skip", "skip"]
    body = _put(client, reports_admin, preview["id"], [{"index": 5, "choice": "import"}]).json()
    assert [_row(body, i)["choice"] for i in group] == ["skip", "import"]


def test_choices_wait_for_a_ready_preview_and_belong_to_its_owner(
    client,
    db,
    make_user,
    uploads,
    reports_admin,
) -> None:
    preview = _ready(client, reports_admin)
    other = admin_with(make_user, "reports")
    assert _put(client, other, preview["id"], CHOICES).status_code == 404
    assert _confirm(client, other, preview["id"]).status_code == 404
    row = db.get(LegacyImportPreview, uuid.UUID(preview["id"]))
    row.status = "fetching"
    db.flush()
    response = _put(client, reports_admin, preview["id"], CHOICES)
    assert response.status_code == 409
    assert response.json()["code"] == "preview_not_ready"
    assert _confirm(client, reports_admin, preview["id"]).json()["code"] == "preview_not_ready"


# --- confirm ---


def test_confirm_refused_while_rows_wait(client, db, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    _put(client, reports_admin, preview["id"], CHOICES[:-2])
    response = _confirm(client, reports_admin, preview["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "preview_choices_missing"
    assert response.json()["indexes"] == [13, 14]  # CHOICES[:-2] leaves out rows 13 and 14
    assert _count(db, LegacySubscriber) == 0


def test_confirm_saves_the_chosen_rows(client, db, uploads, reports_admin) -> None:
    preview = _ready(client, reports_admin)
    assert _put(client, reports_admin, preview["id"], CHOICES).status_code == 200
    response = _confirm(client, reports_admin, preview["id"])
    assert response.status_code == 201, response.text
    summary = response.json()
    assert summary == {
        "import_id": summary["import_id"],
        "rows": 13,
        "imported": 11,
        "skipped": 2,
        "already_imported": 0,
        "not_counted": 2,
        "incomplete": 2,
        "corrected": 1,
        "skipped_numbers": ["xyz", "T3C-012"],
        "incomplete_numbers": ["T3C-010", "T3C-012"],
    }
    # SC-001: every row ends imported or knowingly skipped.
    assert summary["imported"] + summary["skipped"] == summary["rows"]

    imp = db.get(LegacyImport, summary["import_id"])
    assert (imp.created_by, imp.file_name, imp.rows_total, imp.imported) == (
        reports_admin.id,
        "legacy.csv",
        13,
        11,
    )
    subs = {s.legacy_number: s for s in db.scalars(select(LegacySubscriber))}
    assert len(subs) == 11
    first = subs["T3C-001"]
    assert first.import_id == imp.id
    assert (first.first_name, first.second_name, first.third_name) == ("سمير", "تجريبي", "نموذج")
    assert first.full_name == "سمير تجريبي نموذج"
    assert first.phone == "07811110002"
    assert first.family_key == "1111A0000000000002"
    assert first.status_text == "تم" and first.counts_in_check is True
    assert first.extra["mother_name"] == "عينة"
    assert first.extra["email_1"] == "sample@example.com"
    assert first.form_submitted_at.isoformat() == "2024-05-01T07:00:00+00:00"
    assert first.incomplete is False
    corrected = subs["T3C-005"]
    assert corrected.family_number_file == "1111A000000006"
    assert corrected.family_number == CORRECTED
    assert corrected.family_key == CORRECTED
    invalid_phone = subs["T3C-006"]
    assert invalid_phone.phone is None and invalid_phone.phone_file == "0781111"
    assert subs["T3C-009"].counts_in_check is False
    assert subs["T3C-010"].counts_in_check is False and subs["T3C-010"].incomplete is True
    assert subs["T3C-012"].incomplete is True
    assert subs["T3C-012"].first_name == "هادي"  # row 13 imported, row 14 skipped

    images = list(db.scalars(select(LegacyImage)))
    assert len(images) == 19
    assert {
        (i.subscriber.legacy_number, i.side)
        for i in images
        if i.subscriber.legacy_number == "T3C-010"
    } == {("T3C-010", "front")}
    # Files of skipped rows are removed; files of imported rows stay.
    stored = {p.name for p in uploads.iterdir()}
    assert stored == {i.file_name for i in images}
    assert db.get(LegacyImportPreview, uuid.UUID(preview["id"])) is None


def test_the_import_is_audited_once_without_personal_data(
    client, db, uploads, reports_admin
) -> None:
    preview = _ready(client, reports_admin)
    _put(client, reports_admin, preview["id"], CHOICES)
    summary = _confirm(client, reports_admin, preview["id"]).json()
    entries = list(db.scalars(select(AuditLog).where(AuditLog.action == "legacy.imported")))
    assert len(entries) == 1
    entry = entries[0]
    assert (entry.actor_id, entry.entity_type, entry.entity_id) == (
        reports_admin.id,
        "legacy_import",
        str(summary["import_id"]),
    )
    assert entry.after == {
        "file_name": "legacy.csv",
        "rows": 13,
        "imported": 11,
        "skipped": 2,
        "already_imported": 0,
        "not_counted": 2,
        "incomplete": 2,
        "corrected": 1,
    }
    blob = json.dumps([entry.before, entry.after], ensure_ascii=False)
    for personal in ("0781111", "1111A", "سمير", CORRECTED, "sample@example.com"):
        assert personal not in blob


def test_a_new_conflict_before_confirming_refuses_and_flags_the_row(
    client,
    db,
    make_user,
    uploads,
    reports_admin,
) -> None:
    preview = _ready(client, reports_admin)
    _put(client, reports_admin, preview["id"], CHOICES)
    request = request_factory(
        db, make_user("marketer"), status="pending_review", phone="07811110003"
    )
    db.flush()
    response = _confirm(client, reports_admin, preview["id"])
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "preview_changed"
    row3 = _row(body["preview"], 3)
    assert {"code": "in_sijil", "requests": [request.number_label]} in row3["flags"]
    assert row3["choice"] is None
    # Choices of rows whose flags did not change are kept.
    assert _row(body["preview"], 4)["choice"] == "import"
    assert _count(db, LegacySubscriber) == 0
    # After choosing for the new row, the import goes through.
    _put(client, reports_admin, preview["id"], [{"index": 3, "choice": "skip"}])
    assert _confirm(client, reports_admin, preview["id"]).json()["imported"] == 10


def test_a_failure_while_saving_leaves_nothing(
    client, db, uploads, reports_admin, monkeypatch
) -> None:
    preview = _ready(client, reports_admin)
    _put(client, reports_admin, preview["id"], CHOICES)
    files_before = {p.name for p in uploads.iterdir()}

    def broken(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(audit_service, "record", broken)
    with pytest.raises(RuntimeError):
        _confirm(client, reports_admin, preview["id"])
    assert _count(db, LegacySubscriber) == 0
    assert _count(db, LegacyImport) == 0
    assert _count(db, LegacyImage) == 0
    # The preview and its staged files are kept: the admin can confirm again.
    assert db.get(LegacyImportPreview, uuid.UUID(preview["id"])) is not None
    assert {p.name for p in uploads.iterdir()} == files_before


def test_a_reupload_adds_nothing_and_changes_nothing(client, db, uploads, reports_admin) -> None:
    first = _ready(client, reports_admin)
    _put(client, reports_admin, first["id"], CHOICES)
    _confirm(client, reports_admin, first["id"])
    before = {
        s.legacy_number: (s.id, s.full_name, s.phone, s.family_number, s.incomplete)
        for s in db.scalars(select(LegacySubscriber))
    }
    images_before = {i.id for i in db.scalars(select(LegacyImage))}

    again = _ready(client, reports_admin)
    assert again["counts"]["already_imported"] == 12  # every row but the one without a number
    assert again["images_total"] == 2  # only row 12 (no legacy number) is fetched again
    _put(client, reports_admin, again["id"], [{"index": 12, "choice": "skip"}])
    summary = _confirm(client, reports_admin, again["id"]).json()
    assert (summary["imported"], summary["already_imported"], summary["skipped"]) == (0, 12, 1)
    after = {
        s.legacy_number: (s.id, s.full_name, s.phone, s.family_number, s.incomplete)
        for s in db.scalars(select(LegacySubscriber))
    }
    assert after == before
    assert {i.id for i in db.scalars(select(LegacyImage))} == images_before


def test_a_second_preview_confirmed_after_the_first_imports_nothing_twice(
    client,
    db,
    make_user,
    uploads,
    reports_admin,
) -> None:
    """Two admins preview the same file; the second confirms after the first saved (research R10:
    one confirmation at a time). Its rows became «مستورد سابقاً»: nothing is imported twice."""
    other = admin_with(make_user, "reports")
    one = _ready(client, reports_admin)
    two = _ready(client, other)
    _put(client, reports_admin, one["id"], CHOICES)
    _put(client, other, two["id"], CHOICES)
    assert _confirm(client, reports_admin, one["id"]).json()["imported"] == 11
    summary = _confirm(client, other, two["id"]).json()
    assert summary["imported"] == 0
    assert summary["already_imported"] == 12
    assert _count(db, LegacySubscriber) == 11
