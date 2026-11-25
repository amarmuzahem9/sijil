"""Re-importing the SAS file (specs/015 US5: FR-021, FR-022; research R7, R10). `sas_sample_2.csv`
is the first file with one row added (ALM03-07810000021), one phone and expiry changed
(KZF06-07810000002) and one row removed (ALM03-07810000019). Synthetic data only."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models import AuditLog, SasSubscriber, SasSubscriberChange
from app.services import match_service
from tests.helpers import sas
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for

URL = "/api/admin/imports/sas/previews"
FIRST = sas.fixture_bytes("sas_sample.csv")
SECOND = sas.fixture_bytes("sas_sample_2.csv")
FIRST_CHOICES = [
    {"index": 8, "choice": "skip"},
    {"index": 9, "choice": "import"},
    {"index": 10, "choice": "skip"},
    {"index": 14, "choice": "import"},
]
AGAIN_CHOICES = [
    {"index": 8, "choice": "skip"},
    {"index": 9, "choice": "import"},
    {"index": 10, "choice": "skip"},
]
CHANGED = "KZF06-07810000002"
REMOVED = "ALM03-07810000019"
ADDED = "ALM03-07810000021"


@pytest.fixture
def reporter(make_user):
    return admin_with(make_user, "reports")


@pytest.fixture
def first_import(client, db, make_user, reporter) -> dict:
    towers = sas.seed_towers(db)
    request_factory(db, make_user("marketer"), status="pending_review", phone="07810000014")
    db.flush()
    summary = _import(
        client,
        reporter,
        FIRST,
        FIRST_CHOICES,
        [{"prefix": "ZZQ07", "tower_id": towers["ALM03"]}],
    )
    assert summary["added"] == 16
    return {"towers": towers, "summary": summary}


def _preview(client, user, data: bytes) -> dict:
    res = client.post(
        URL, files={"file": ("sas.csv", data, "text/csv")}, headers=headers_for(client, user)
    )
    assert res.status_code == 201, res.text
    return res.json()


def _import(client, user, data: bytes, choices, prefixes=None) -> dict:
    preview = _preview(client, user, data)
    put = client.put(
        f"{URL}/{preview['id']}/choices",
        json={"choices": choices, "prefixes": prefixes or []},
        headers=headers_for(client, user),
    )
    assert put.status_code == 200, put.json()
    done = client.post(f"{URL}/{preview['id']}/confirm", headers=headers_for(client, user))
    assert done.status_code == 201, done.json()
    return done.json()


def _sub(db, key: str) -> SasSubscriber:
    db.expire_all()
    return db.scalar(select(SasSubscriber).where(SasSubscriber.username_key == key))


def test_the_second_preview_counts_new_updates_unchanged_and_missing(
    client, first_import, reporter
) -> None:
    preview = _preview(client, reporter, SECOND)
    counts = preview["counts"]
    assert (counts["rows"], counts["new"], counts["update"], counts["unchanged"]) == (18, 2, 2, 14)
    assert counts["missing_from_file"] == 1
    # The prefix mapped the first time is not asked again.
    assert preview["prefixes"] == [
        {
            "prefix": "ZZQ07",
            "rows": 2,
            "tower_id": first_import["towers"]["ALM03"],
            "from_previous": True,
            "chosen": True,
        }
    ]
    assert preview["waiting_prefixes"] == 0
    flagged = {row["index"]: row for row in preview["flagged"]}
    assert set(flagged) == {8, 9, 10}  # the stored phone of row 14 is not asked again
    assert (flagged[9]["kind"], flagged[10]["kind"]) == ("unchanged", "update")


def test_the_second_confirm_updates_adds_and_marks_the_missing_row(
    client, db, first_import, reporter
) -> None:
    untouched = _sub(db, "KZF06-07810000013")
    untouched_at = untouched.updated_at
    first_id = first_import["summary"]["import_id"]

    summary = _import(client, reporter, SECOND, AGAIN_CHOICES)
    assert {k: summary[k] for k in ("added", "updated", "unchanged", "skipped")} == {
        "added": 1,
        "updated": 1,
        "unchanged": 14,
        "skipped": 2,
    }
    assert (summary["missing_marked"], summary["missing_cleared"], summary["prefixes_mapped"]) == (
        1,
        0,
        0,
    )
    second_id = summary["import_id"]

    changed = _sub(db, CHANGED)
    assert (changed.phone, changed.expires_at) == (
        "07810000022",
        datetime(2026, 12, 31, 21, 0, tzinfo=UTC),
    )
    assert (changed.first_import_id, changed.last_import_id) == (first_id, second_id)
    (change,) = db.scalars(
        select(SasSubscriberChange).where(SasSubscriberChange.sas_subscriber_id == changed.id)
    )
    assert change.import_id == second_id
    assert change.before == {
        "phone": "07810000002",
        "phone_file": "07810000002",
        "expires_at": "2026-11-30T21:00:00+00:00",
    }
    assert change.after == {
        "phone": "07810000022",
        "phone_file": "07810000022",
        "expires_at": "2026-12-31T21:00:00+00:00",
    }
    assert db.scalar(select(func.count()).select_from(SasSubscriberChange)) == 1

    added = _sub(db, ADDED)
    assert (added.first_import_id, added.last_import_id) == (second_id, second_id)

    unchanged = _sub(db, "KZF06-07810000013")
    assert unchanged.updated_at == untouched_at
    assert unchanged.last_import_id == first_id

    removed = _sub(db, REMOVED)
    assert removed.missing_since is not None
    assert removed.missing_import_id == second_id

    # «تخطي» on an update row leaves the stored row as it is, and it is not marked missing.
    kept = _sub(db, "ALM03-07810000008")
    assert (kept.phone, kept.sas_id, kept.missing_since) == ("07810000008", "108", None)

    (entry,) = db.scalars(
        select(AuditLog).where(
            AuditLog.action == "sas.imported", AuditLog.entity_id == str(second_id)
        )
    )
    assert (entry.after["missing_marked"], entry.after["updated"]) == (1, 1)


def test_the_mark_stays_once_and_clears_when_the_row_returns(
    client, db, first_import, reporter
) -> None:
    second = _import(client, reporter, SECOND, AGAIN_CHOICES)
    marked = _sub(db, REMOVED)
    since, by = marked.missing_since, marked.missing_import_id

    third = _import(client, reporter, SECOND, AGAIN_CHOICES)
    assert (third["missing_marked"], third["missing_cleared"]) == (0, 0)
    still = _sub(db, REMOVED)
    assert (still.missing_since, still.missing_import_id) == (since, by)
    assert by == second["import_id"]

    fourth = _import(client, reporter, FIRST, AGAIN_CHOICES)
    assert fourth["missing_cleared"] == 1
    assert fourth["missing_marked"] == 1  # ALM03-07810000021 is not in the first file
    back = _sub(db, REMOVED)
    assert (back.missing_since, back.missing_import_id) == (None, None)
    assert _sub(db, ADDED).missing_import_id == fourth["import_id"]


def test_phones_follow_the_latest_file_and_missing_rows_still_match(
    client, db, first_import, reporter
) -> None:
    _import(client, reporter, SECOND, AGAIN_CHOICES)
    changed = _sub(db, CHANGED)
    removed = _sub(db, REMOVED)

    def sas_refs(phone: str) -> set[str]:
        found = match_service.find_matches(db, phone=phone).records
        return {r.ref_id for r in found if r.source == "sas"}

    assert str(changed.id) in sas_refs("07810000022")  # the new phone column
    assert str(changed.id) in sas_refs("07810000002")  # still inside its username (FR-012)
    assert str(removed.id) in sas_refs("07810000019")  # missing rows still count (FR-022)
