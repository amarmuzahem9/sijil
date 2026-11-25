"""A SAS file of 20 000 rows (specs/015 T053; plan › Performance Goals: preview and confirm each
under 30 s on the staging server). A second import of the same file is all «بلا تغيير» and
writes no change row. Generated synthetic rows only."""

import time

import pytest
from sqlalchemy import func, select

from app.models import SasSubscriber, SasSubscriberChange
from tests.helpers import sas
from tests.helpers.review import admin_with, headers_for

URL = "/api/admin/imports/sas/previews"
ROWS = 20_000
LIMIT_SECONDS = 30
HEADER = sas.fixture_rows("sas_sample.csv")[0]


def _file() -> bytes:
    body = [
        [
            str(50_000 + i),
            f"ALM03-079{i:08d}",
            "مشترك",
            "حجم",
            f"079{i:08d}",
            "2026-12-01 00:00:00",
            "",
            "admin",
            f"SYNTH-PW-V{i}",
            "2025-01-10 10:00:00",
            "2026-11-20 08:00:00",
            "PLUS",
        ]
        for i in range(ROWS)
    ]
    return sas.to_csv([HEADER, *body])


def _timed(action):
    started = time.perf_counter()
    result = action()
    return result, time.perf_counter() - started


@pytest.mark.slow
def test_twenty_thousand_rows_preview_and_confirm_in_time(client, db, make_user) -> None:
    sas.seed_towers(db)
    reporter = admin_with(make_user, "reports")
    h = headers_for(client, reporter)
    data = _file()

    def preview():
        return client.post(URL, files={"file": ("big.csv", data, "text/csv")}, headers=h)

    def confirm(preview_id):
        return lambda: client.post(f"{URL}/{preview_id}/confirm", headers=h)

    first, seconds = _timed(preview)
    assert first.status_code == 201, first.text[:500]
    assert first.json()["counts"]["new"] == ROWS
    assert first.json()["flagged"] == []
    assert seconds < LIMIT_SECONDS, f"preview took {seconds:.1f} s"
    done, seconds = _timed(confirm(first.json()["id"]))
    assert done.status_code == 201, done.text[:500]
    assert done.json()["added"] == ROWS
    assert seconds < LIMIT_SECONDS, f"confirm took {seconds:.1f} s"
    assert db.scalar(select(func.count()).select_from(SasSubscriber)) == ROWS

    again, seconds = _timed(preview)
    assert again.json()["counts"]["unchanged"] == ROWS
    assert seconds < LIMIT_SECONDS, f"second preview took {seconds:.1f} s"
    done, seconds = _timed(confirm(again.json()["id"]))
    assert done.json()["unchanged"] == ROWS
    assert seconds < LIMIT_SECONDS, f"second confirm took {seconds:.1f} s"
    assert db.scalar(select(func.count()).select_from(SasSubscriberChange)) == 0
