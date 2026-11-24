"""Two admins decide the same request at once: exactly one decision is stored (specs/010 FR-009,
SC-003, research R2).

Like test_submit_concurrency this test commits, so each thread has its own connection, and it
removes every row it made at the end. Synthetic data only.
"""

import threading
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Area, AuditLog, Notification, Plan, Request, RequestReason, Tower, User
from app.schemas.admin_requests import AcceptIn, RejectIn
from app.services import review_service
from tests.helpers.requests import request_factory

ROUNDS = 5


@pytest.fixture
def world(engine):
    tag = uuid.uuid4().hex[:6].upper()
    with Session(engine) as s:
        area = Area(name=f"منطقة قرار {tag}")
        s.add(area)
        s.flush()
        tower = Tower(code=f"DC{tag}", name="برج قرار", area_id=area.id)
        plan = Plan(name=f"DEC{tag}", trial_price=1, second_price=2)
        s.add_all([tower, plan])
        users = [
            User(
                name=f"مستخدم قرار {i}",
                phone=f"0774{uuid.uuid4().int % 10**7:07d}",
                password_hash="x",
                role=role,
                permissions=["review"] if role == "admin" else [],
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
        s.execute(delete(RequestReason).where(RequestReason.request_id.in_(req_ids)))
        s.execute(delete(Request).where(Request.id.in_(req_ids)))
        s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids["users"])))
        s.execute(delete(User).where(User.id.in_(ids["users"])))
        s.execute(delete(Tower).where(Tower.id == ids["tower"]))
        s.execute(delete(Plan).where(Plan.id == ids["plan"]))
        s.execute(delete(Area).where(Area.id == ids["area"]))
        s.commit()


def _pending(engine, world) -> int:
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
        return request.id


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_two_admins_one_decision(engine, world, round_) -> None:
    request_id = _pending(engine, world)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def decide(admin_id: int, action: str) -> None:
        with Session(engine) as s:
            admin = s.get(User, admin_id)
            barrier.wait()
            try:
                if action == "accept":
                    review_service.accept(s, admin, request_id, AcceptIn())
                else:
                    review_service.reject(s, admin, request_id, RejectIn(reason="card_unclear"))
                result = action
            except AppError as err:
                s.rollback()
                result = err.code
        with lock:
            outcomes.append(result)

    threads = [
        threading.Thread(target=decide, args=(world["users"][1], "accept")),
        threading.Thread(target=decide, args=(world["users"][2], "reject")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert sorted(outcomes) in (["accept", "already_decided"], ["already_decided", "reject"])
    with Session(engine) as s:
        request = s.get(Request, request_id)
        decided = [request.approved_by is not None, request.rejected_by is not None]
        assert decided.count(True) == 1
        assert request.status == ("approved" if "accept" in outcomes else "rejected")
        entries = s.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "request",
                AuditLog.entity_id == str(request.number),
                AuditLog.action.in_(("request.approved", "request.rejected")),
            )
        ).all()
        assert len(entries) == 1
        # specs/012 FR-017: one notification, for the decision that won.
        kinds = s.scalars(
            select(Notification.kind).where(Notification.request_id == request_id)
        ).all()
        assert kinds == [request.status]
