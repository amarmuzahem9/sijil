"""A deletion racing an accept, or another deletion: the first one wins (specs/011 research R3).

Like test_admin_decide_concurrency this test commits, so each thread has its own connection, and it
removes every row it made at the end. Synthetic data only.
"""

import threading
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Area, AuditLog, Plan, Request, RequestReason, Tower, User
from app.schemas.admin_requests import AcceptIn, DeleteIn
from app.services import deletion_service, review_service
from tests.helpers.requests import request_factory

ROUNDS = 4


@pytest.fixture
def world(engine):
    tag = uuid.uuid4().hex[:6].upper()
    with Session(engine) as s:
        area = Area(name=f"منطقة حذف {tag}")
        s.add(area)
        s.flush()
        tower = Tower(code=f"DL{tag}", name="برج حذف", area_id=area.id)
        plan = Plan(name=f"DEL{tag}", trial_price=1, second_price=2)
        s.add_all([tower, plan])
        users = [
            User(
                name=f"مستخدم حذف {i}",
                phone=f"0775{uuid.uuid4().int % 10**7:07d}",
                password_hash="x",
                role=role,
                permissions=["review", "delete"] if role == "admin" else [],
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
        s.execute(delete(RequestReason).where(RequestReason.request_id.in_(req_ids)))
        s.execute(delete(Request).where(Request.id.in_(req_ids)))
        s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids["users"])))
        s.execute(delete(User).where(User.id.in_(ids["users"])))
        s.execute(delete(Tower).where(Tower.id == ids["tower"]))
        s.execute(delete(Plan).where(Plan.id == ids["plan"]))
        s.execute(delete(Area).where(Area.id == ids["area"]))
        s.commit()


def _pending(engine, world) -> tuple[int, str]:
    with Session(engine) as s:
        marketer = s.get(User, world["users"][0])
        request = request_factory(
            s,
            marketer,
            status="pending_review",
            area=s.get(Area, world["area"]),
            tower=s.get(Tower, world["tower"]),
            plan=s.get(Plan, world["plan"]),
        )
        s.commit()
        return request.id, request.number_label


def _race(engine, world, actions: tuple[str, str]) -> tuple[int, list[str]]:
    request_id, label = _pending(engine, world)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def act(admin_id: int, action: str) -> None:
        with Session(engine) as s:
            admin = s.get(User, admin_id)
            barrier.wait()
            try:
                if action == "accept":
                    review_service.accept(s, admin, request_id, AcceptIn())
                else:
                    body = DeleteIn(reason="duplicate", confirm_number=label)
                    deletion_service.delete(s, admin, request_id, body)
                result = action
            except AppError as err:
                s.rollback()
                result = err.code
        with lock:
            outcomes.append(result)

    threads = [
        threading.Thread(target=act, args=(world["users"][1], actions[0])),
        threading.Thread(target=act, args=(world["users"][2], actions[1])),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return request_id, outcomes


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_delete_and_accept(engine, world, round_) -> None:
    request_id, outcomes = _race(engine, world, ("delete", "accept"))
    assert sorted(outcomes) in (["accept", "request_not_deletable"], ["delete", "request_deleted"])
    with Session(engine) as s:
        request = s.get(Request, request_id)
        if "delete" in outcomes:
            assert request.is_deleted and request.status == "pending_review"
        else:
            assert not request.is_deleted and request.status == "approved"


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_delete_and_delete(engine, world, round_) -> None:
    request_id, outcomes = _race(engine, world, ("delete", "delete"))
    assert sorted(outcomes) == ["delete", "request_deleted"]
    with Session(engine) as s:
        number = s.get(Request, request_id).number
        entries = s.scalars(
            select(AuditLog).where(
                AuditLog.action == "request.deleted", AuditLog.entity_id == str(number)
            )
        ).all()
        assert len(entries) == 1
