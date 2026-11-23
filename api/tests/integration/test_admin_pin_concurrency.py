"""A pin runs at the same time as a submission or another pin (specs/010 research R4).

- A pin to family F and a marketer submission with family F: whichever runs second sees the other,
  so the family link is never missed.
- Two pins with swapped national IDs (X from A to B, Y from B to A): both finish, no deadlock.

Like test_submit_concurrency this test commits, so each thread has its own connection, and it
removes every row it made at the end. Synthetic data only.
"""

import threading
import uuid

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core.family_key import family_key
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import (
    Area,
    AuditLog,
    Draft,
    DraftImage,
    Plan,
    Request,
    RequestImage,
    RequestNumberPin,
    RequestReason,
    Tower,
    User,
)
from app.schemas.admin_requests import PinIn
from app.services import otp_service, review_service, submit_service
from tests.helpers.requests import request_factory

ROUNDS = 5


@pytest.fixture
def world(engine):
    tag = uuid.uuid4().hex[:6].upper()
    made: dict = {"drafts": []}
    with Session(engine) as s:
        area = Area(name=f"منطقة تثبيت {tag}")
        s.add(area)
        s.flush()
        tower = Tower(code=f"PN{tag}", name="برج تثبيت", area_id=area.id)
        plan = Plan(name=f"PIN{tag}", trial_price=1, second_price=2)
        s.add_all([tower, plan])
        users = [
            User(
                name=f"مستخدم تثبيت {i}",
                phone=f"0775{uuid.uuid4().int % 10**7:07d}",
                password_hash="x",
                role=role,
                permissions=["review"] if role == "admin" else [],
            )
            for i, role in enumerate(("marketer", "marketer", "admin", "admin"))
        ]
        s.add_all(users)
        s.flush()
        made.update(area=area.id, tower=tower.id, plan=plan.id, users=[u.id for u in users])
        s.commit()
    yield made
    with Session(engine) as s:
        req_ids = list(s.scalars(select(Request.id).where(Request.tower_id == made["tower"])))
        s.execute(delete(RequestNumberPin).where(RequestNumberPin.request_id.in_(req_ids)))
        s.execute(delete(RequestImage).where(RequestImage.request_id.in_(req_ids)))
        s.execute(delete(RequestReason).where(RequestReason.request_id.in_(req_ids)))
        s.execute(delete(Request).where(Request.id.in_(req_ids)))
        s.execute(delete(Draft).where(Draft.id.in_(made["drafts"])))
        s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(made["users"])))
        s.execute(delete(User).where(User.id.in_(made["users"])))
        s.execute(delete(Tower).where(Tower.id == made["tower"]))
        s.execute(delete(Plan).where(Plan.id == made["plan"]))
        s.execute(delete(Area).where(Area.id == made["area"]))
        s.commit()


def _catalog(s: Session, world) -> dict:
    return {
        "area": s.get(Area, world["area"]),
        "tower": s.get(Tower, world["tower"]),
        "plan": s.get(Plan, world["plan"]),
    }


def _pending(s: Session, world, *, card_fields: dict, fields: list[str], **overrides) -> Request:
    request = request_factory(
        s,
        s.get(User, world["users"][0]),
        status="pending_review",
        card_fields=card_fields,
        **_catalog(s, world),
        **overrides,
    )
    s.add(RequestReason(request_id=request.id, reason="numbers_edited", details={"fields": fields}))
    s.flush()
    return request


def _ready_draft(s: Session, world, *, national_id: str, family: str) -> Draft:
    """A verified, complete draft of marketer 2 that confirmed «اشتراك إضافي» for `family`."""
    c = _catalog(s, world)
    today = utc_now().date()
    phone = f"078099{uuid.uuid4().int % 10**5:05d}"
    draft = Draft(
        id=uuid.uuid4(),
        marketer_id=world["users"][1],
        first_name="تجربة",
        father_name="اختبار",
        grandfather_name="نموذج",
        great_grandfather_name="مثال",
        surname="التجريبي",
        mother_first_name="عينة",
        mother_second_name="نموذجية",
        full_name="تجربة اختبار نموذج مثال التجريبي",
        national_id=national_id,
        family_number=family,
        birth_date=today.replace(year=1999),
        issue_date=today.replace(year=2021),
        expiry_date=today.replace(year=2031),
        birth_place="بغداد",
        issuing_authority="مديرية الجنسية والمعلومات المدنية",
        location_lat=34.7,
        location_lng=43.68,
        location_source="gps",
        address="حي تجريبي",
        landmark="قرب نقطة",
        area_id=c["area"].id,
        tower_id=c["tower"].id,
        plan_id=c["plan"].id,
        area_name=c["area"].name,
        tower_code=c["tower"].code,
        plan_name=c["plan"].name,
        trial_price=c["plan"].trial_price,
        second_price=c["plan"].second_price,
        phone_input=phone,
        phone_normalized=phone,
    )
    draft.additional_confirmed_key = family_key(family)
    draft.otp_verified_at = utc_now()
    draft.otp_context_hash = otp_service.context_hash(draft)
    s.add(draft)
    s.flush()
    for side in ("front", "back"):
        s.add(
            DraftImage(
                draft_id=draft.id,
                side=side,
                file_name=f"{uuid.uuid4().hex}.jpg",
                size_bytes=1,
                width=1,
                height=1,
                uploaded_by=world["users"][1],
            )
        )
    world["drafts"].append(draft.id)
    return draft


def _race(engine, jobs) -> list[str]:
    """Run each job (a function of a session) in its own thread and connection at once."""
    engine = create_engine(engine.url, pool_size=len(jobs) + 2, max_overflow=0)
    barrier = threading.Barrier(len(jobs), timeout=30)
    results: list[str] = [""] * len(jobs)

    def run(i, job):
        with Session(engine) as s:
            barrier.wait()
            try:
                job(s)
                results[i] = "ok"
            except AppError as err:
                s.rollback()
                results[i] = err.code
            except Exception as err:  # a deadlock surfaces here
                s.rollback()
                results[i] = type(err).__name__

    threads = [threading.Thread(target=run, args=(i, j)) for i, j in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    engine.dispose()
    return results


def _pin_job(admin_id: int, request_id: int, body: PinIn):
    def job(s: Session) -> None:
        review_service.pin(s, s.get(User, admin_id), request_id, body)

    return job


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_pin_and_submission_on_one_family(engine, world, round_) -> None:
    n = uuid.uuid4().int % 10**6
    family = f"4444D{n:013d}"
    with Session(engine) as s:
        x = _pending(
            s,
            world,
            card_fields={"family_number": {"original": family, "edited": True}},
            fields=["family_number"],
        )
        draft = _ready_draft(s, world, national_id=f"199155{n:06d}", family=family)
        s.commit()
        x_id, draft_id, version = x.id, draft.id, draft.version

    def submit(s: Session) -> None:
        submit_service.submit(s, s.get(User, world["users"][1]), draft_id, version)

    results = _race(
        engine,
        [_pin_job(world["users"][2], x_id, PinIn(field="family_number", source="reading")), submit],
    )

    assert results == ["ok", "ok"]
    with Session(engine) as s:
        new = s.scalars(select(Request).where(Request.draft_id == draft_id)).one()
        links = s.scalars(
            select(RequestReason).where(
                RequestReason.reason == "family_exists",
                RequestReason.state == "open",
                RequestReason.request_id.in_((x_id, new.id)),
            )
        ).all()
        pairs = {(r.request_id, r.matched_ref) for r in links}
        assert (new.id, str(x_id)) in pairs or (x_id, str(new.id)) in pairs


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_swapped_pins_do_not_deadlock(engine, world, round_) -> None:
    n = uuid.uuid4().int % 10**6
    a, b = f"199266{n:06d}", f"199277{n:06d}"
    with Session(engine) as s:
        x = _pending(
            s, world, card_fields={}, fields=["national_id"], national_id=a, national_id_input=a
        )
        y = _pending(
            s, world, card_fields={}, fields=["national_id"], national_id=b, national_id_input=b
        )
        s.commit()
        x_id, y_id = x.id, y.id

    results = _race(
        engine,
        [
            _pin_job(world["users"][2], x_id, PinIn(field="national_id", source="typed", value=b)),
            _pin_job(world["users"][3], y_id, PinIn(field="national_id", source="typed", value=a)),
        ],
    )

    assert results == ["ok", "ok"]
    with Session(engine) as s:
        assert (s.get(Request, x_id).national_id, s.get(Request, y_id).national_id) == (b, a)
