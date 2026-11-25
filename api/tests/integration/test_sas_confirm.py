"""SAS import choices and confirmation (specs/015 US1, FR-006–FR-010; research R9, R10, R12;
contracts/api.md). Synthetic SAS file only."""

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.models import (
    AuditLog,
    SasImport,
    SasImportPreview,
    SasSubscriber,
    SasSubscriberChange,
    SasTowerMapping,
)
from app.services import audit_service
from app.services.import_lock import IMPORT_CONFIRM_LOCK
from tests.helpers import sas
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for

URL = "/api/admin/imports/sas/previews"
SAMPLE = sas.fixture_bytes("sas_sample.csv")
CHOICES = [
    {"index": 8, "choice": "skip"},
    {"index": 9, "choice": "import"},
    {"index": 10, "choice": "skip"},
    {"index": 14, "choice": "import"},
]


@pytest.fixture
def reports_admin(make_user):
    return admin_with(make_user, "reports")


@pytest.fixture
def seeded(db, make_user) -> dict:
    towers = sas.seed_towers(db)
    marketer = make_user("marketer")
    pending = request_factory(db, marketer, status="pending_review", phone="07810000014")
    request_factory(db, marketer, phone="07810000015", username="ALM03-07810000015")
    request_factory(db, marketer, status="rejected", phone="07810000018")
    db.flush()
    return {"towers": towers, "marketer": marketer, "pending": pending}


def _preview(client, user) -> dict:
    response = client.post(
        URL, files={"file": ("sas.csv", SAMPLE, "text/csv")}, headers=headers_for(client, user)
    )
    assert response.status_code == 201, response.text
    return response.json()


def _put(client, user, preview_id, choices=None, prefixes=None):
    body = {"choices": choices or [], "prefixes": prefixes or []}
    return client.put(f"{URL}/{preview_id}/choices", json=body, headers=headers_for(client, user))


def _confirm(client, user, preview_id):
    return client.post(f"{URL}/{preview_id}/confirm", headers=headers_for(client, user))


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def _row(preview: dict, index: int) -> dict:
    return next(r for r in preview["flagged"] if r["index"] == index)


def _ready_to_confirm(client, user, seeded) -> dict:
    preview = _preview(client, user)
    mapped = [{"prefix": "ZZQ07", "tower_id": seeded["towers"]["KZF06"]}]
    response = _put(client, user, preview["id"], CHOICES, mapped)
    assert response.status_code == 200, response.text
    return response.json()


# --- choices --------------------------------------------------------------------------------------


def test_choices_and_prefixes_are_saved_partially(client, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    first = _put(client, reports_admin, preview["id"], [{"index": 9, "choice": "import"}])
    assert first.status_code == 200
    body = first.json()
    assert _row(body, 9)["choice"] == "import"
    assert body["counts"]["waiting_choice"] == 3
    assert body["waiting_prefixes"] == 1
    tower = seeded["towers"]["ALM03"]
    second = _put(
        client, reports_admin, preview["id"], prefixes=[{"prefix": "ZZQ07", "tower_id": tower}]
    ).json()
    assert second["prefixes"] == [
        {"prefix": "ZZQ07", "rows": 2, "tower_id": tower, "from_previous": False, "chosen": True}
    ]
    assert second["waiting_prefixes"] == 0
    assert _row(second, 9)["choice"] == "import"


def test_no_tower_is_a_valid_mapping(client, db, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    body = _put(
        client, reports_admin, preview["id"], prefixes=[{"prefix": "ZZQ07", "tower_id": None}]
    ).json()
    assert body["prefixes"][0]["chosen"] is True
    assert body["prefixes"][0]["tower_id"] is None
    rows = {r["index"]: r for r in db.get(SasImportPreview, uuid.UUID(preview["id"])).rows}
    assert rows[6]["tower_id"] is None
    assert rows[6]["tower_source"] == "mapping"


@pytest.mark.parametrize(
    "choices",
    [
        [{"index": 8, "choice": "import"}],  # username_missing is skip only
        [{"index": 9, "choice": "import"}, {"index": 10, "choice": "import"}],  # one per username
        [{"index": 2, "choice": "skip"}],  # not a flagged row
        [{"index": 999, "choice": "skip"}],  # no such row
    ],
)
def test_choices_not_allowed(client, seeded, reports_admin, choices) -> None:
    preview = _preview(client, reports_admin)
    response = _put(client, reports_admin, preview["id"], choices)
    assert response.status_code == 422
    assert response.json()["code"] == "choice_not_allowed"


def test_prefix_problems(client, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    unknown_tower = _put(
        client, reports_admin, preview["id"], prefixes=[{"prefix": "ZZQ07", "tower_id": 9_999_999}]
    )
    assert unknown_tower.status_code == 422
    assert unknown_tower.json()["code"] == "tower_not_found"
    unknown_prefix = _put(
        client, reports_admin, preview["id"], prefixes=[{"prefix": "NOPE", "tower_id": None}]
    )
    assert unknown_prefix.status_code == 422
    assert unknown_prefix.json()["code"] == "choice_not_allowed"


def test_skip_all_for_a_group_then_change_one_row(client, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    group = [{"index": 9, "choice": "skip"}, {"index": 10, "choice": "skip"}]
    assert _put(client, reports_admin, preview["id"], group).status_code == 200
    body = _put(client, reports_admin, preview["id"], [{"index": 10, "choice": "import"}]).json()
    assert _row(body, 9)["choice"] == "skip"
    assert _row(body, 10)["choice"] == "import"


def test_choices_belong_to_the_owner(client, make_user, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    other = admin_with(make_user, "reports")
    response = _put(client, other, preview["id"], [{"index": 9, "choice": "skip"}])
    assert response.status_code == 404
    assert response.json()["code"] == "preview_not_found"
    confirmed = _confirm(client, other, preview["id"])
    assert confirmed.status_code == 404
    assert confirmed.json()["code"] == "preview_not_found"


# --- confirmation ---------------------------------------------------------------------------------


def test_confirm_refused_while_rows_or_prefixes_wait(client, db, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    response = _confirm(client, reports_admin, preview["id"])
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "preview_choices_missing"
    assert body["indexes"] == [8, 9, 10, 14]
    assert body["prefixes"] == ["ZZQ07"]
    _put(client, reports_admin, preview["id"], CHOICES)
    only_prefix = _confirm(client, reports_admin, preview["id"]).json()
    assert only_prefix["indexes"] == []
    assert only_prefix["prefixes"] == ["ZZQ07"]
    assert _count(db, SasSubscriber) == 0


def test_confirm_saves_the_chosen_rows(client, db, seeded, reports_admin) -> None:
    preview = _ready_to_confirm(client, reports_admin, seeded)
    response = _confirm(client, reports_admin, preview["id"])
    assert response.status_code == 201, response.text
    summary = response.json()
    record = db.get(SasImport, summary["import_id"])
    assert summary == {
        "import_id": record.id,
        "rows": 18,
        "added": 16,
        "updated": 0,
        "unchanged": 0,
        "skipped": 2,
        "missing_marked": 0,
        "missing_cleared": 0,
        "without_phone": 1,
        "prefixes_mapped": 1,
        "skipped_rows": [{"index": 8, "sas_id": "107"}, {"index": 10, "sas_id": "109"}],
    }
    assert (record.created_by, record.file_name, record.rows_total, record.added) == (
        reports_admin.id,
        "sas.csv",
        18,
        16,
    )
    assert _count(db, SasSubscriber) == 16
    assert _count(db, SasSubscriberChange) == 0
    towers = seeded["towers"]
    subs = {s.username_key: s for s in db.scalars(select(SasSubscriber))}
    two_phones = subs["KZF06-07810000013"]
    assert two_phones.username == "KZF06-07810000013"
    assert two_phones.sas_id == "112"
    assert (two_phones.first_name, two_phones.last_name) == ("مشترك", "تجريبي")
    assert two_phones.full_name == "مشترك تجريبي"
    assert (two_phones.phone, two_phones.phone_file) == ("07810000099", "07810000099")
    assert two_phones.username_phone == "07810000013"
    assert (two_phones.tower_prefix, two_phones.tower_id) == ("KZF06", towers["KZF06"])
    assert two_phones.expires_at == datetime(2026, 11, 30, 21, 0, tzinfo=UTC)
    assert two_phones.sas_created_at == datetime(2025, 1, 10, 7, 0, tzinfo=UTC)
    assert two_phones.last_online_at == datetime(2026, 11, 20, 5, 0, tzinfo=UTC)
    assert (two_phones.group_name, two_phones.parent_name, two_phones.notes) == (
        "PLUS",
        "admin",
        None,
    )
    assert two_phones.first_import_id == two_phones.last_import_id == record.id
    assert two_phones.missing_since is None
    assert subs["RBD-01S-07810000003"].tower_id == towers["RBD01S"]
    assert subs["ZZQ07-07810000005"].tower_id == towers["KZF06"]  # the admin's mapping
    assert subs["LEGACYUSER"].tower_id is None
    assert subs["LEGACYUSER"].phone is None
    assert subs["ALM03-07810000011"].phone is None  # invalid column, the username phone counts
    assert subs["ALM03-07810000011"].phone_file == "12345"
    assert subs["ALM03-07810000008"].sas_id == "108"  # the chosen one of the repeated rows
    assert subs["ALM03-07810000019"].expires_at is None  # SAS «never»
    mapping = db.get(SasTowerMapping, "ZZQ07")
    assert (mapping.tower_id, mapping.set_by, mapping.import_id) == (
        towers["KZF06"],
        reports_admin.id,
        record.id,
    )
    # The preview is gone.
    assert db.get(SasImportPreview, uuid.UUID(preview["id"])) is None


def test_the_import_is_audited_once_without_personal_data(
    client, db, seeded, reports_admin
) -> None:
    preview = _ready_to_confirm(client, reports_admin, seeded)
    summary = _confirm(client, reports_admin, preview["id"]).json()
    entries = list(db.scalars(select(AuditLog).where(AuditLog.action == "sas.imported")))
    assert len(entries) == 1
    entry = entries[0]
    assert (entry.actor_id, entry.entity_type, entry.entity_id) == (
        reports_admin.id,
        "sas_import",
        str(summary["import_id"]),
    )
    assert entry.after == {
        "file_name": "sas.csv",
        "rows": 18,
        "added": 16,
        "updated": 0,
        "unchanged": 0,
        "skipped": 2,
        "missing_marked": 0,
        "missing_cleared": 0,
        "without_phone": 1,
        "prefixes_mapped": 1,
    }
    blob = json.dumps([entry.before, entry.after], ensure_ascii=False)
    for personal in ("0781000", "ALM03-", "LEGACYUSER", "مشترك", "ZZQ07"):
        assert personal not in blob


def test_a_new_conflict_before_confirming_refuses_and_flags_the_row(
    client, db, seeded, reports_admin
) -> None:
    preview = _ready_to_confirm(client, reports_admin, seeded)
    request = request_factory(db, seeded["marketer"], status="pending_review", phone="07810000001")
    db.flush()
    response = _confirm(client, reports_admin, preview["id"])
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "preview_changed"
    row2 = _row(body["preview"], 2)
    assert row2["flags"] == [{"code": "phone_in_sijil", "requests": [request.number_label]}]
    assert row2["choice"] is None
    # Choices of rows whose flags did not change are kept.
    assert _row(body["preview"], 9)["choice"] == "import"
    assert body["preview"]["waiting_prefixes"] == 0
    assert _count(db, SasSubscriber) == 0
    _put(client, reports_admin, preview["id"], [{"index": 2, "choice": "skip"}])
    assert _confirm(client, reports_admin, preview["id"]).json()["added"] == 15


def test_a_failure_while_saving_leaves_nothing(
    client, db, seeded, reports_admin, monkeypatch
) -> None:
    preview = _ready_to_confirm(client, reports_admin, seeded)

    def broken(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr(audit_service, "record", broken)
    with pytest.raises(RuntimeError):
        _confirm(client, reports_admin, preview["id"])
    for model in (SasSubscriber, SasImport, SasTowerMapping, SasSubscriberChange):
        assert _count(db, model) == 0, model
    # The preview is kept: the admin can confirm again.
    assert db.get(SasImportPreview, uuid.UUID(preview["id"])) is not None


def test_confirm_waits_on_the_lock_shared_with_the_legacy_import(
    client, db, engine, seeded, reports_admin
) -> None:
    preview = _ready_to_confirm(client, reports_admin, seeded)
    holder = engine.connect()
    try:
        holder.execute(text("SELECT pg_advisory_lock(:key)"), {"key": IMPORT_CONFIRM_LOCK})
        db.execute(text("SET LOCAL lock_timeout = '300ms'"))
        with pytest.raises(OperationalError, match="lock timeout"):
            _confirm(client, reports_admin, preview["id"])
    finally:
        holder.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": IMPORT_CONFIRM_LOCK})
        holder.close()
