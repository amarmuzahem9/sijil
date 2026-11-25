"""SAS import preview (specs/015 US1, FR-001–FR-005, FR-018; research R2–R9, R12;
contracts/api.md). Synthetic SAS file only."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.timeutil import utc_now
from app.models import SasImport, SasImportPreview, SasSubscriber, SasTowerMapping
from tests.helpers import sas
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for

URL = "/api/admin/imports/sas/previews"
SAMPLE = sas.fixture_bytes("sas_sample.csv")
EXPECTED = sas.expected()


@pytest.fixture
def reports_admin(make_user):
    return admin_with(make_user, "reports")


@pytest.fixture
def seeded(db, make_user) -> dict:
    """The towers and the three requests of expected.json's note."""
    towers = sas.seed_towers(db)
    marketer = make_user("marketer")
    pending = request_factory(db, marketer, status="pending_review", phone="07810000014")
    approved = request_factory(db, marketer, phone="07810000015", username="ALM03-07810000015")
    rejected = request_factory(db, marketer, status="rejected", phone="07810000018")
    db.flush()
    return {
        "towers": towers,
        "marketer": marketer,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
    }


def _upload(client, user, data: bytes = SAMPLE, name: str = "sas.csv"):
    return client.post(
        URL, files={"file": (name, data, "text/csv")}, headers=headers_for(client, user)
    )


def _preview(client, user, data: bytes = SAMPLE) -> dict:
    response = _upload(client, user, data)
    assert response.status_code == 201, response.text
    return response.json()


def _by_index(preview: dict) -> dict[int, dict]:
    return {row["index"]: row for row in preview["flagged"]}


# --- permissions and file problems ---------------------------------------------------------------


def test_main_admin_and_reports_admin_may_upload(client, make_user, seeded, reports_admin) -> None:
    assert _upload(client, make_user("super_admin")).status_code == 201
    assert _upload(client, reports_admin).status_code == 201


@pytest.mark.parametrize(
    "who",
    [
        ("admin", ["review"]),
        ("admin", ["link"]),
        ("admin", ["review", "link", "marketers", "settings"]),
        ("marketer", []),
    ],
)
def test_others_are_refused_on_every_route(client, make_user, seeded, reports_admin, who) -> None:
    preview = _preview(client, reports_admin)
    role, perms = who
    user = make_user(role)
    user.permissions = perms
    headers = headers_for(client, user)
    responses = [
        _upload(client, user),
        client.get(f"{URL}/{preview['id']}", headers=headers),
        client.delete(f"{URL}/{preview['id']}", headers=headers),
    ]
    for response in responses:
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "forbidden"


def test_another_admins_preview_is_not_found(client, make_user, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    other = admin_with(make_user, "reports")
    got = client.get(f"{URL}/{preview['id']}", headers=headers_for(client, other))
    assert got.status_code == 404
    assert got.json()["code"] == "preview_not_found"
    gone = client.delete(f"{URL}/{preview['id']}", headers=headers_for(client, other))
    assert gone.status_code == 404


def test_missing_columns_are_named(client, seeded, reports_admin) -> None:
    rows = sas.fixture_rows("sas_sample.csv")
    keep = [i for i, h in enumerate(rows[0]) if h != "username"]
    response = _upload(client, reports_admin, sas.to_csv([[r[i] for i in keep] for r in rows]))
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "import_columns_missing"
    assert body["columns"] == ["username"]
    assert "username" in body["message"]


def test_unreadable_too_large_and_too_many_rows(client, seeded, reports_admin, monkeypatch) -> None:
    unreadable = _upload(client, reports_admin, b"%PDF-1.7\n\x00\xff binary", "x.pdf")
    assert unreadable.status_code == 422
    assert unreadable.json()["code"] == "import_file_unreadable"

    from app.services import legacy_file

    monkeypatch.setattr(legacy_file, "SAS_MAX_ROWS", 5)
    many = _upload(client, reports_admin)
    assert many.status_code == 422
    assert many.json()["code"] == "import_too_many_rows"
    monkeypatch.setattr(legacy_file, "SAS_MAX_FILE_BYTES", 100)
    large = _upload(client, reports_admin)
    assert large.status_code == 413
    assert large.json()["code"] == "import_file_too_large"


def test_a_file_larger_than_the_legacy_limit_is_accepted(client, seeded, reports_admin) -> None:
    header, *body = sas.fixture_rows("sas_sample.csv")
    rows = [header] + [
        [str(1000 + i), f"ALM03-0782{i:07d}", "مشترك", "تجريبي", f"0782{i:07d}"] + row[5:]
        for i, row in enumerate(body * 150)  # 2 700 rows > the legacy 2 000
    ]
    preview = _preview(client, reports_admin, sas.to_csv(rows))
    assert preview["counts"]["rows"] == 2700


# --- the preview ---------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_counts_prefixes_and_flags_match_the_fixture(
    client, db, seeded, reports_admin, kind
) -> None:
    data = SAMPLE if kind == "csv" else sas.to_xlsx(sas.fixture_rows("sas_sample.csv"))
    preview = _preview(client, reports_admin, data)
    assert preview["file_name"] == "sas.csv"
    assert preview["counts"] == EXPECTED["counts"]
    assert preview["prefixes"] == EXPECTED["prefixes"]
    assert preview["waiting_prefixes"] == 1
    flagged = _by_index(preview)
    pending = seeded["pending"].number_label
    expected = {
        int(index): [
            f | {"requests": [pending]} if f["code"] == "phone_in_sijil" else f for f in flags
        ]
        for index, flags in EXPECTED["flagged"].items()
    }
    assert {index: row["flags"] for index, row in flagged.items()} == expected
    assert flagged[8]["allowed"] == ["skip"]
    assert flagged[9]["allowed"] == ["import", "skip"]
    assert all(row["choice"] is None for row in preview["flagged"])
    assert all(row["kind"] == "new" for row in preview["flagged"])
    # Flagged rows carry what the admin decides on.
    assert flagged[10]["username"] == "alm03-07810000008"
    assert flagged[10]["phone"] == "07810000009"
    assert flagged[10]["username_phone"] == "07810000008"
    assert flagged[14]["sas_id"] == "113"
    assert flagged[14]["full_name"] == "مشترك تجريبي"


def test_nothing_is_saved_by_an_upload(client, db, seeded, reports_admin) -> None:
    _preview(client, reports_admin)
    for model in (SasSubscriber, SasImport, SasTowerMapping):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert db.scalar(select(func.count()).select_from(SasImportPreview)) == 1


def test_towers_by_the_rule_on_the_stored_preview_rows(client, db, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    rows = {r["index"]: r for r in db.get(SasImportPreview, preview["id"]).rows}
    towers = seeded["towers"]
    for index, code in EXPECTED["towers"].items():
        assert rows[int(index)]["tower_id"] == (towers[code] if code else None), index
    assert rows[6]["tower_id"] is None
    assert rows[6]["tower_source"] == "unmapped"


def test_saved_mapping_is_pre_filled(client, db, make_user, seeded, reports_admin) -> None:
    admin = make_user("super_admin")
    record = SasImport(
        created_by=admin.id,
        file_name="old.csv",
        **dict.fromkeys(
            (
                "rows_total",
                "added",
                "updated",
                "unchanged",
                "skipped",
                "missing_marked",
                "missing_cleared",
                "without_phone",
                "prefixes_mapped",
            ),
            0,
        ),
    )
    db.add(record)
    db.flush()
    tower = seeded["towers"]["KZF06"]
    db.add(SasTowerMapping(prefix="ZZQ07", tower_id=tower, set_by=admin.id, import_id=record.id))
    db.flush()
    preview = _preview(client, reports_admin)
    assert preview["prefixes"] == [
        {"prefix": "ZZQ07", "rows": 2, "tower_id": tower, "from_previous": True, "chosen": True}
    ]
    assert preview["waiting_prefixes"] == 0
    rows = {r["index"]: r for r in db.get(SasImportPreview, preview["id"]).rows}
    assert rows[6]["tower_id"] == tower
    assert rows[6]["tower_source"] == "mapping"


def test_only_live_active_requests_flag_a_phone(client, db, seeded, reports_admin) -> None:
    mark_deleted(db, seeded["pending"], seeded["marketer"])
    db.flush()
    flagged = _by_index(_preview(client, reports_admin))
    assert 14 not in flagged  # the deleted request frees the phone (§7.4)
    assert 18 not in flagged  # a rejected request never counts (§6.1)


def test_a_new_upload_replaces_the_previous_preview(client, db, seeded, reports_admin) -> None:
    first = _preview(client, reports_admin)
    second = _preview(client, reports_admin)
    assert db.get(SasImportPreview, first["id"]) is None
    old = client.get(f"{URL}/{first['id']}", headers=headers_for(client, reports_admin))
    assert old.status_code == 404
    got = client.get(f"{URL}/{second['id']}", headers=headers_for(client, reports_admin))
    assert got.status_code == 200
    assert got.json()["counts"] == EXPECTED["counts"]


def test_cancel_removes_the_preview(client, db, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    headers = headers_for(client, reports_admin)
    assert client.delete(f"{URL}/{preview['id']}", headers=headers).status_code == 204
    assert db.get(SasImportPreview, preview["id"]) is None


def test_an_expired_preview_is_not_found_and_swept(client, db, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    row = db.get(SasImportPreview, preview["id"])
    row.expires_at = utc_now() - timedelta(seconds=1)
    db.flush()
    got = client.get(f"{URL}/{preview['id']}", headers=headers_for(client, reports_admin))
    assert got.status_code == 404
    assert got.json()["code"] == "preview_not_found"
    assert db.scalar(select(func.count()).select_from(SasImportPreview)) == 0


def test_the_preview_expires_after_one_hour(client, db, seeded, reports_admin) -> None:
    preview = _preview(client, reports_admin)
    row = db.get(SasImportPreview, preview["id"])
    assert timedelta(minutes=59) < row.expires_at - row.created_at <= timedelta(hours=1)
