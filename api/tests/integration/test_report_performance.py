"""«التقارير والتصدير» stays fast with thousands of subscribers (specs/019 SC-001, SC-002, FR-017;
research R3, R5, R6). Synthetic data, inserted in bulk.

The export runs on its worker thread while the report is asked again, so the data lives in a
scratch database with real commits (the shared test session is one connection).
"""

import threading
import time
import uuid
import zipfile
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Area, Export, Plan, Request, RequestImage, Tower, User
from app.schemas.reports import ReportFilters
from app.services import export_service, report_service
from tests.conftest import API_ROOT
from tests.helpers.card_images import scenario_jpeg
from tests.helpers.requests import request_factory

pytestmark = pytest.mark.slow

TOTAL = 20_000
WITH_IMAGES = 1_000
START = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
NOVEMBER = ReportFilters.model_validate(
    {"period": "range", "from": "2026-11-01", "to": "2026-11-30"}
)
REPORT_LIMIT_S = 2.0
EXPORT_LIMIT_S = 120.0

_COPY = """
INSERT INTO requests (number, draft_id, submitted_at, otp_verified_at, approved_at, {cols})
SELECT nextval('request_number_seq'), gen_random_uuid(),
       CAST(:start AS timestamptz) + g * interval '1 minute',
       CAST(:start AS timestamptz) + g * interval '1 minute',
       CAST(:start AS timestamptz) + g * interval '1 minute', {cols}
FROM requests t, generate_series(CAST(:first AS integer), CAST(:last AS integer)) g
WHERE t.id = :template
"""


@pytest.fixture
def scratch(engine):
    """A fresh database at head, with real commits."""
    url = engine.url.set(database=f"{engine.url.database}_perf19")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    try:
        yield eng
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()


def _place(db: Session, code: str) -> dict:
    area = Area(name=f"منطقة سرعة {code}")
    db.add(area)
    db.flush()
    tower = Tower(code=code, name=f"برج سرعة {code}", area_id=area.id)
    plan = Plan(name=f"فئة سرعة {code}", trial_price=20000, second_price=35000)
    db.add_all([tower, plan])
    db.flush()
    return {"area": area, "tower": tower, "plan": plan}


def _seed(eng, uploads) -> dict:
    with Session(eng) as db:
        marketers = []
        for i in range(20):
            user = User(
                name=f"مسوّق سرعة {i}",
                phone=f"0773{i:07d}",
                password_hash="synthetic",
                role="marketer",
                permissions=[],
            )
            db.add(user)
            marketers.append(user)
        boss = User(
            name="أدمن سرعة",
            phone="07739999999",
            password_hash="synthetic",
            role="super_admin",
            permissions=[],
        )
        db.add(boss)
        db.flush()
        bulk, images = _place(db, "SPDA"), _place(db, "SPDB")
        cols = ", ".join(
            c.key
            for c in Request.__table__.columns
            if c.key
            not in ("id", "number", "draft_id", "submitted_at", "otp_verified_at", "approved_at")
        )
        plan = [
            (bulk, 1, TOTAL - WITH_IMAGES - 1),
            (images, TOTAL - WITH_IMAGES + 1, TOTAL - 1),
        ]
        for i, (place, first, last) in enumerate(plan):
            template = request_factory(
                db,
                marketers[i],
                **place,
                submitted_at=START,
                otp_verified_at=START,
                approved_at=START,
            )
            db.execute(
                text(_COPY.format(cols=cols)),
                {"start": START, "first": first, "last": last, "template": template.id},
            )
            # Spread the copies over the marketers.
            db.execute(
                text("UPDATE requests SET marketer_id = :m WHERE tower_id = :t AND id % 20 = :k"),
                [{"m": m.id, "t": place["tower"].id, "k": k} for k, m in enumerate(marketers)],
            )
        jpeg = scenario_jpeg("clear_front", 120, 76)
        ids = list(db.scalars(select(Request.id).where(Request.tower_id == images["tower"].id)))
        assert len(ids) == WITH_IMAGES
        rows = []
        for request_id in ids:
            for side in ("front", "back"):
                name = f"{uuid.uuid4().hex}.jpg"
                (uploads / name).write_bytes(jpeg)
                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "request_id": request_id,
                        "side": side,
                        "file_name": name,
                        "size_bytes": len(jpeg),
                        "width": 120,
                        "height": 76,
                        "uploaded_by": marketers[0].id,
                        "created_at": START,
                    }
                )
        db.execute(insert(RequestImage), rows)
        db.commit()
        assert db.scalar(select(text("count(*)")).select_from(Request)) == TOTAL
        return {"boss_id": boss.id, "image_tower": images["tower"].id}


def _report_seconds(eng) -> float:
    with Session(eng) as db:
        t0 = time.perf_counter()
        where = report_service.conditions(NOVEMBER)
        total = report_service.count(db, where)
        report_service.page(db, NOVEMBER, where, 1)
        report_service.summaries(db, where)
        elapsed = time.perf_counter() - t0
    assert total == TOTAL
    return elapsed


def test_report_and_export_at_size(scratch, tmp_path, monkeypatch, exports_dir) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(get_settings(), "uploads_dir", str(uploads))
    seeded = _seed(scratch, uploads)

    # SC-001: the report with its summaries over 20,000 requests.
    _report_seconds(scratch)  # warm up
    report = _report_seconds(scratch)
    print(f"\nSC-001 report over {TOTAL} requests: {report:.3f} s")
    assert report < REPORT_LIMIT_S

    # SC-002: an identity export of 1,000 requests with their images, built on its thread while
    # the report is asked again.
    monkeypatch.setattr(export_service, "submit", lambda export_id: None)
    with Session(scratch) as db:
        boss = db.get(User, seeded["boss_id"])
        filters = NOVEMBER.model_copy(update={"tower_id": seeded["image_tower"]})
        export_id = export_service.create(db, boss, filters, include_identity=True).id

    def build() -> None:
        with Session(scratch) as job:
            export_service.run(export_id, session=job)

    t0 = time.perf_counter()
    worker = threading.Thread(target=build)
    worker.start()
    during = []
    while worker.is_alive() and len(during) < 20:
        during.append(_report_seconds(scratch))
    worker.join(timeout=EXPORT_LIMIT_S)
    built = time.perf_counter() - t0
    assert not worker.is_alive()
    print(f"SC-002 export of {WITH_IMAGES} requests with images ready in {built:.2f} s")
    if during:
        print(f"SC-002 report while building: max {max(during):.3f} s over {len(during)} calls")
    assert built < EXPORT_LIMIT_S
    assert all(seconds < REPORT_LIMIT_S for seconds in during)

    with Session(scratch) as db:
        export = db.get(Export, export_id)
        assert export.state == "ready", export.error_code
        assert export.row_count == WITH_IMAGES and export.missing_images == 0
        url = export_service.issue_ticket(db, db.get(User, seeded["boss_id"]), export_id)
        ticket = url.split("ticket=")[1]
        t0 = time.perf_counter()
        download = export_service.open_download(db, export_id, ticket)
        archive = tmp_path / "export.zip"
        with archive.open("wb") as out:
            for chunk in export_service.stream_zip(download):
                out.write(chunk)
        streamed = time.perf_counter() - t0
    names = zipfile.ZipFile(archive).namelist()
    print(f"SC-002 ZIP of {len(names)} files streamed in {streamed:.2f} s")
    assert len(names) == 1 + 2 * WITH_IMAGES
