"""Two admins press «تم الربط» on the same request at once: one link is stored (specs/013 FR-006,
SC-004, research R2).

Like test_admin_decide_concurrency this test commits, so each thread has its own connection, and
it removes every row it made at the end. Synthetic data only.
"""

import threading
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    Area,
    AuditLog,
    Notification,
    Plan,
    Request,
    RequestLink,
    Tower,
    User,
)
from app.services import link_service
from tests.helpers.requests import request_factory

ROUNDS = 5


@pytest.fixture
def world(engine):
    tag = uuid.uuid4().hex[:6].upper()
    with Session(engine) as s:
        area = Area(name=f"منطقة ربط {tag}")
        s.add(area)
        s.flush()
        tower = Tower(code=f"LC{tag}", name="برج ربط", area_id=area.id)
        plan = Plan(name=f"LNK{tag}", trial_price=1, second_price=2)
        s.add_all([tower, plan])
        users = [
            User(
                name=f"مستخدم ربط {i}",
                phone=f"0772{uuid.uuid4().int % 10**7:07d}",
                password_hash="x",
                role=role,
                permissions=["link"] if role == "admin" else [],
            )
            for i, role in enumerate(("marketer", "admin", "admin"))
        ]
        s.add_all(users)
        s.flush()
        ids = {"area": area.id, "tower": tower.id, "plan": plan.id, "users": [u.id for u in users]}
        s.commit()
    yield ids
    with Session(engine) as s:
        req_ids = list(s.scalars(select(Request.id).where(Request.tower_id == ids["tower"])))
        s.execute(delete(Notification).where(Notification.request_id.in_(req_ids)))
        s.execute(delete(RequestLink).where(RequestLink.request_id.in_(req_ids)))
        s.execute(delete(Request).where(Request.id.in_(req_ids)))
        s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids["users"])))
        s.execute(delete(User).where(User.id.in_(ids["users"])))
        s.execute(delete(Tower).where(Tower.id == ids["tower"]))
        s.execute(delete(Plan).where(Plan.id == ids["plan"]))
        s.execute(delete(Area).where(Area.id == ids["area"]))
        s.commit()


def _accepted(engine, world) -> int:
    with Session(engine) as s:
        request = request_factory(
            s,
            s.get(User, world["users"][0]),
            status="approved",
            area=s.get(Area, world["area"]),
            tower=s.get(Tower, world["tower"]),
            plan=s.get(Plan, world["plan"]),
        )
        s.commit()
        return request.id


def _race(engine, world, action) -> list[str]:
    """Both admins run `action(session, admin)` behind one barrier; the outcome codes."""
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def run(admin_id: int) -> None:
        with Session(engine) as s:
            admin = s.get(User, admin_id)
            barrier.wait()
            try:
                action(s, admin)
                result = "ok"
            except AppError as err:
                s.rollback()
                result = err.code
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=run, args=(uid,)) for uid in world["users"][1:]]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return sorted(outcomes)


def _writes(engine, request_id: int, kind: str, action: str) -> tuple[int, int, int]:
    with Session(engine) as s:
        number = s.get(Request, request_id).number
        history = s.scalars(
            select(RequestLink).where(
                RequestLink.request_id == request_id, RequestLink.kind == kind
            )
        ).all()
        audits = s.scalars(
            select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == str(number))
        ).all()
        notes = s.scalars(
            select(Notification).where(
                Notification.request_id == request_id, Notification.kind == kind
            )
        ).all()
        return len(history), len(audits), len(notes)


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_two_admins_one_link(engine, world, round_) -> None:
    request_id = _accepted(engine, world)

    outcomes = _race(engine, world, lambda s, admin: link_service.link(s, admin, request_id))

    assert outcomes == ["already_linked", "ok"]
    with Session(engine) as s:
        request = s.get(Request, request_id)
        assert request.status == "linked"
        assert request.linked_by in world["users"][1:]
    assert _writes(engine, request_id, "linked", "request.linked") == (1, 1, 1)
