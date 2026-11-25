"""`ct_password` is never read into Sijil (specs/015 FR-003, SC-003; constitution II; research R3).

Every `ct_password` cell of the synthetic files holds a unique marker `SYNTH-PW-<n>`. After each
step the markers are searched in the API responses, every `sas_*` table (as text), the audit log
and the captured log output: none may appear anywhere.
"""

import logging

import pytest
from sqlalchemy import text

from tests.helpers import sas
from tests.helpers.review import admin_with, headers_for

URL = "/api/admin/imports/sas/previews"
MARKERS = sas.passwords()
_TABLES = (
    "sas_imports",
    "sas_subscribers",
    "sas_subscriber_changes",
    "sas_tower_mappings",
    "sas_import_previews",
    "audit_log",
)


def _stored_text(db) -> str:
    return "\n".join(
        str(row)
        for table in _TABLES
        for row in db.execute(text(f"SELECT t::text FROM {table} t"))  # noqa: S608
    )


def _found(haystack: str) -> list[str]:
    return [marker for marker in MARKERS if marker in haystack]


def _files() -> dict[str, bytes]:
    rows = sas.fixture_rows("sas_sample.csv")
    upper = [[h.upper() if h == "ct_password" else h for h in rows[0]], *rows[1:]]
    return {
        "csv": sas.fixture_bytes("sas_sample.csv"),
        "xlsx": sas.to_xlsx(rows),
        "upper-case header": sas.to_csv(upper),
    }


@pytest.fixture
def reports_admin(make_user):
    return admin_with(make_user, "reports")


def test_the_fixture_really_holds_the_markers() -> None:
    assert len(_found(sas.fixture_bytes("sas_sample.csv").decode("utf-8"))) == 18


@pytest.mark.parametrize("kind", ["csv", "xlsx", "upper-case header"])
def test_no_marker_after_upload_and_reads(client, db, reports_admin, caplog, kind) -> None:
    caplog.set_level(logging.DEBUG)
    sas.seed_towers(db)
    headers = headers_for(client, reports_admin)
    created = client.post(
        URL, files={"file": ("sas.csv", _files()[kind], "text/csv")}, headers=headers
    )
    assert created.status_code == 201, created.text
    got = client.get(f"{URL}/{created.json()['id']}", headers=headers)
    assert got.status_code == 200

    assert _found(created.text) == []
    assert _found(got.text) == []
    assert _found(_stored_text(db)) == []
    assert _found(caplog.text) == []


def test_no_marker_in_a_refusal(client, db, reports_admin, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    rows = sas.fixture_rows("sas_sample.csv")
    keep = [i for i, h in enumerate(rows[0]) if h != "phone"]
    response = client.post(
        URL,
        files={"file": ("sas.csv", sas.to_csv([[r[i] for i in keep] for r in rows]), "text/csv")},
        headers=headers_for(client, reports_admin),
    )
    assert response.status_code == 422
    assert _found(response.text) == []
    assert _found(caplog.text) == []
    assert _found(_stored_text(db)) == []
