"""20 marketers submit the same phone (or national ID) at once: exactly one passes
(specs/008 SC-004, research R6 step 6).

Unlike the other tests this one commits, so each thread has its own connection, and it removes
every row it made at the end. Synthetic data only.
"""

import threading
import uuid

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

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
    RequestReason,
    Tower,
    User,
)
from app.services import otp_service, submit_service

N = 20
PHONE = "07807770000"


@pytest.fixture
def world(engine):
    made: dict = {"users": [], "drafts": []}
    tag = uuid.uuid4().hex[:6].upper()
    with Session(engine) as s:
        area = Area(name=f"منطقة تزامن {tag}")
        s.add(area)
        s.flush()
        tower = Tower(code=f"CC{tag}", name="برج تزامن", area_id=area.id)
        plan = Plan(name=f"CONC{tag}", trial_price=1, second_price=2)
        s.add_all([tower, plan])
        s.flush()
        made["catalog"] = (area.id, tower.id, plan.id)
        s.commit()
    yield made
    area_id, tower_id, plan_id = made["catalog"]
    with Session(engine) as s:
        req_ids = list(s.scalars(select(Request.id).where(Request.tower_id == tower_id)))
        s.execute(delete(RequestImage).where(RequestImage.request_id.in_(req_ids)))
        s.execute(delete(RequestReason).where(RequestReason.request_id.in_(req_ids)))
        s.execute(delete(Request).where(Request.id.in_(req_ids)))
        s.execute(delete(Draft).where(Draft.id.in_(made["drafts"])))
        s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(made["users"])))
        s.execute(delete(User).where(User.id.in_(made["users"])))
        s.execute(delete(Tower).where(Tower.id == tower_id))
        s.execute(delete(Plan).where(Plan.id == plan_id))
        s.execute(delete(Area).where(Area.id == area_id))
        s.commit()


def _ready_drafts(engine, world, *, same_phone: bool, same_nid: bool) -> list[tuple]:
    """N verified, complete drafts of N marketers. Rows only: submission reads no files."""
    area_id, tower_id, plan_id = world["catalog"]
    today = utc_now().date()
    with Session(engine) as s:
        area, tower, plan = s.get(Area, area_id), s.get(Tower, tower_id), s.get(Plan, plan_id)
        for i in range(N):
            user = User(
                name=f"مسوّق تزامن {i}",
                phone=f"0773{uuid.uuid4().int % 10**7:07d}",
                password_hash="x",
                role="marketer",
                permissions=[],
            )
            s.add(user)
            s.flush()
            phone = PHONE if same_phone else f"078088{i:05d}"
            draft = Draft(
                id=uuid.uuid4(),
                marketer_id=user.id,
                first_name="تجربة",
                father_name="اختبار",
                grandfather_name="نموذج",
                great_grandfather_name="مثال",
                surname="التجريبي",
                mother_first_name="عينة",
                mother_second_name="نموذجية",
                full_name="تجربة اختبار نموذج مثال التجريبي",
                national_id="199933330000" if same_nid else f"19993333{i:04d}",
                family_number=f"3333C{i:013d}",
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
                area_id=area.id,
                tower_id=tower.id,
                plan_id=plan.id,
                area_name=area.name,
                tower_code=tower.code,
                plan_name=plan.name,
                trial_price=plan.trial_price,
                second_price=plan.second_price,
                phone_input=phone,
                phone_normalized=phone,
            )
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
                        uploaded_by=user.id,
                    )
                )
            world["users"].append(user.id)
            world["drafts"].append(draft.id)
        s.commit()
        return [
            (d.marketer_id, d.id, d.version) for d in (s.get(Draft, i) for i in world["drafts"])
        ]


def _race(engine, drafts) -> list[str]:
    # Each thread holds a connection while it waits at the barrier: the pool must fit them all.
    engine = create_engine(engine.url, pool_size=len(drafts) + 2, max_overflow=0)
    barrier = threading.Barrier(len(drafts), timeout=30)
    results: list[str] = []
    guard = threading.Lock()

    def run(user_id, draft_id, version):
        with Session(engine) as s:
            user = s.get(User, user_id)
            barrier.wait()
            try:
                submit_service.submit(s, user, draft_id, version)
                outcome = "created"
            except AppError as err:
                outcome = err.code
        with guard:
            results.append(outcome)

    threads = [threading.Thread(target=run, args=d) for d in drafts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    engine.dispose()
    return results


def test_same_phone_one_winner(engine, world) -> None:
    results = _race(engine, _ready_drafts(engine, world, same_phone=True, same_nid=False))
    assert sorted(results) == ["created"] + ["phone_used"] * (N - 1)


def test_same_national_id_one_winner(engine, world) -> None:
    results = _race(engine, _ready_drafts(engine, world, same_phone=False, same_nid=True))
    assert sorted(results) == ["created"] + ["national_id_exists"] * (N - 1)
