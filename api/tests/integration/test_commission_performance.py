"""The report stays fast at the size of the company (specs/017 T054, plan › Performance Goals):
a month with 50 marketers and 3,000 links, some of them paid, builds in under 1 s. Synthetic data,
inserted in bulk so the setup itself stays short."""

import time
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import insert, select

from app.models import CommissionPayment, CommissionPaymentRequest, Request, RequestLink
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
MARKETERS = 50
LINKS = 3000


def test_a_big_month_builds_in_under_a_second(client, db, make_user, frozen_clock) -> None:
    frozen_clock.set(NOW)
    boss = admin_with(make_user, "commissions")
    marketers = [make_user("marketer") for _ in range(MARKETERS)]
    # One real row as a template; the rest are bulk copies with their own number, phone and keys.
    template = request_factory(db, marketers[0], status="linked", linked_at=OCTOBER)
    columns = {
        c.key: getattr(template, c.key)
        for c in Request.__table__.columns
        if c.key not in ("id", "number", "draft_id", "phone", "username", "national_id")
    }
    rows = []
    for i in range(LINKS - 1):
        phone = f"079{i + 10_000_000:08d}"
        rows.append(
            columns
            | {
                "marketer_id": marketers[i % MARKETERS].id,
                "number": 900_000 + i,
                "draft_id": uuid.uuid4(),
                "phone": phone,
                "username": f"{template.tower_code}-{phone}",
                "national_id": f"1980{i:08d}",
                "linked_at": OCTOBER + timedelta(minutes=i),
            }
        )
    db.execute(insert(Request), rows)
    ids = db.scalars(select(Request.id).where(Request.number >= 900_000)).all()
    db.execute(
        insert(RequestLink),
        [{"request_id": i, "kind": "linked", "actor_id": boss.id, "at": OCTOBER} for i in ids],
    )
    # Ten marketers are paid, so the paid path (count_today, alerts) is measured too.
    for m in marketers[:10]:
        mine = db.scalars(
            select(Request.id).where(Request.marketer_id == m.id, Request.status == "linked")
        ).all()
        payment = CommissionPayment(
            marketer_id=m.id,
            month=date(2026, 10, 1),
            count=len(mine),
            tier_min_count=50,
            rate=10000,
            amount=10000 * len(mine),
            paid_by=boss.id,
            paid_at=NOW,
        )
        db.add(payment)
        db.flush()
        db.execute(
            insert(CommissionPaymentRequest),
            [{"request_id": r, "payment_id": payment.id} for r in mine],
        )
    db.flush()

    headers = headers_for(client, boss)
    started = time.perf_counter()
    res = client.get("/api/admin/commissions?month=2026-10", headers=headers)
    elapsed = time.perf_counter() - started

    assert res.status_code == 200, res.json()
    body = res.json()
    assert len(body["rows"]) == MARKETERS
    assert sum(r["count"] for r in body["rows"]) == LINKS
    print(f"report of {MARKETERS} marketers and {LINKS} links: {elapsed:.3f}s")
    assert elapsed < 1.0, f"report took {elapsed:.2f}s"
