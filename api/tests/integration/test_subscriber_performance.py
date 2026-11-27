"""«المشتركون» stays fast at the company's size (specs/018 T032, SC-001, SC-002, FR-013):
20,000 SAS rows, 500 legacy rows and 5,000 requests. A phone, a name and a family search return
their first page in under 1 s each, and a file with 20 linked records opens in under 1 s.
Synthetic data, inserted in bulk from one template row per table."""

import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert

from app.models import LegacySubscriber, Request, SasSubscriber
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for
from tests.helpers.sas import sas_subscriber

SAS_ROWS = 20_000
LEGACY_ROWS = 500
REQUESTS = 5_000
T0 = datetime(2026, 1, 1, tzinfo=UTC)
SHARED_PHONE = "07818880000"
SHARED_FAMILY = "1990Q8880000000000"
LIMIT_SECONDS = 1.0


def _columns(model, row, skip):
    return {c.key: getattr(row, c.key) for c in model.__table__.columns if c.key not in skip}


def _seed(db, make_user):
    admin = make_user("super_admin")
    marketers = [make_user("marketer") for _ in range(20)]

    # Requests: one real row per marketer group as a template, then bulk copies.
    template = request_factory(db, marketers[0], status="approved")
    base = _columns(
        Request,
        template,
        {"id", "number", "draft_id", "phone", "username", "national_id", "family_key"},
    )
    db.execute(
        insert(Request),
        [
            base
            | {
                "marketer_id": marketers[i % 20].id,
                "number": 800_000 + i,
                "draft_id": uuid.uuid4(),
                "phone": f"079{20_000_000 + i:08d}",
                "username": f"{template.tower_code}-079{20_000_000 + i:08d}",
                "national_id": f"1970{i:08d}",
                "family_key": f"1970Z{i:013d}",
                "full_name": f"طالب اداء رقم {i % 97} تجريبي",
                "submitted_at": T0 + timedelta(minutes=i),
            }
            for i in range(REQUESTS - 1)
        ],
    )

    legacy_template = legacy_subscriber(db, admin, family_number="1960L0000000000000")
    legacy_base = _columns(
        LegacySubscriber, legacy_template, {"id", "legacy_number", "phone", "family_key"}
    )
    # Legacy numbers are «T3C-» and 3 digits, unique (§12.1): skip the template's own.
    numbers = [
        f"T3C-{n:03d}" for n in range(1000) if f"T3C-{n:03d}" != legacy_template.legacy_number
    ]
    db.execute(
        insert(LegacySubscriber),
        [
            legacy_base
            | {
                "legacy_number": numbers[i],
                "phone": f"077{30_000_000 + i:08d}",
                "family_key": SHARED_FAMILY if i < 10 else f"1960L{i:013d}",
                "full_name": f"قديم اداء {i % 31}",
            }
            for i in range(LEGACY_ROWS - 1)
        ],
    )

    sas_template = sas_subscriber(db, admin, username="PFT01-07740000000")
    sas_base = _columns(
        SasSubscriber,
        sas_template,
        {"id", "username", "username_key", "username_phone", "phone", "sas_id"},
    )
    db.execute(
        insert(SasSubscriber),
        [
            sas_base
            | {
                "username": f"PFT01-077{40_000_001 + i:08d}",
                "username_key": f"PFT01-077{40_000_001 + i:08d}",
                "username_phone": f"077{40_000_001 + i:08d}",
                "phone": SHARED_PHONE if i < 10 else f"077{40_000_001 + i:08d}",
                "full_name": f"مشترك اداء {i % 53} SAS",
                "sas_created_at": T0 - timedelta(minutes=i),
            }
            for i in range(SAS_ROWS - 1)
        ],
    )
    # The record whose file has 20 linked records: 10 SAS by phone, 10 legacy by family.
    target = request_factory(
        db, marketers[1], status="approved", phone=SHARED_PHONE, family_number=SHARED_FAMILY
    )
    db.flush()
    return target


def _timed(client, headers, url, **params):
    started = time.perf_counter()
    res = client.get(url, params=params, headers=headers)
    elapsed = time.perf_counter() - started
    assert res.status_code == 200, (str(res.request.url), res.json())
    return res.json(), elapsed


def test_search_and_file_at_company_size(client, db, make_user) -> None:
    target = _seed(db, make_user)
    headers = headers_for(client, admin_with(make_user, "review"))
    url = "/api/admin/subscribers"

    phone, t_phone = _timed(client, headers, url, q=SHARED_PHONE)
    assert phone["total"] == 11  # the target request and 10 SAS rows
    # A name matching every one of the 20,000 SAS rows: the slowest case of a name search.
    name, t_name = _timed(client, headers, url, q="مشترك اداء")
    assert name["total"] > 50 and len(name["items"]) == 50
    family, t_family = _timed(client, headers, url, q=SHARED_FAMILY)
    assert family["total"] == 11  # the target request and 10 legacy rows
    body, t_file = _timed(client, headers, f"{url}/sijil/{target.id}")
    assert len(body["linked"]) == 20

    print(f"phone {t_phone:.3f}s, name {t_name:.3f}s, family {t_family:.3f}s, file {t_file:.3f}s")
    for label, elapsed in (
        ("phone", t_phone),
        ("name", t_name),
        ("family", t_family),
        ("file", t_file),
    ):
        assert elapsed < LIMIT_SECONDS, f"{label} took {elapsed:.2f}s"
