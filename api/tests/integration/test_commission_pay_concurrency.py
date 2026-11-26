"""«تم الدفع» under concurrency (specs/017 T035, research R5).

Two admins pay the same row at once: one payment. A pay and an undo of one of its requests at
once: the payment never holds an undone request. Like test_link_concurrency these tests commit, so
each thread has its own connection, and they remove every row they made at the end.
"""

import threading
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.timeutil import _set_clock_for_tests
from app.errors import AppError
from app.models import (
    Area,
    AuditLog,
    CommissionPayment,
    CommissionPaymentRequest,
    Notification,
    Plan,
    Request,
    RequestLink,
    Tower,
    User,
)
from app.schemas.admin_links import UnlinkIn
from app.services import commission_service, link_service
from tests.helpers.requests import request_factory

ROUNDS = 5
NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
MONTH = date(2026, 10, 1)


@pytest.fixture
def world(engine):
    _set_clock_for_tests(NOW)
    tag = uuid.uuid4().hex[:6].upper()
    with Session(engine) as s:
        area = Area(name=f"منطقة دفع {tag}")
        s.add(area)
        s.flush()
        tower = Tower(code=f"PC{tag}", name="برج دفع", area_id=area.id)
        plan = Plan(name=f"PAY{tag}", trial_price=1, second_price=2)
        s.add_all([tower, plan])
        users = [
            User(
                name=f"مستخدم دفع {i}",
                phone=f"0773{uuid.uuid4().int % 10**7:07d}",
                password_hash="x",
                role=role,
                permissions=perms,
            )
            for i, (role, perms) in enumerate(
                (("marketer", []), ("admin", ["commissions", "link"]), ("admin", ["commissions"]))
            )
        ]
        s.add_all(users)
        s.flush()
        ids = {"area": area.id, "tower": tower.id, "plan": plan.id, "users": [u.id for u in users]}
        s.commit()
    yield ids
    _set_clock_for_tests(None)
    with Session(engine) as s:
        req_ids = list(s.scalars(select(Request.id).where(Request.tower_id == ids["tower"])))
        pay_ids = list(
            s.scalars(
                select(CommissionPayment.id).where(CommissionPayment.marketer_id == ids["users"][0])
            )
        )
        s.execute(
            delete(CommissionPaymentRequest).where(CommissionPaymentRequest.payment_id.in_(pay_ids))
        )
        s.execute(delete(CommissionPayment).where(CommissionPayment.id.in_(pay_ids)))
        s.execute(delete(Notification).where(Notification.request_id.in_(req_ids)))
        s.execute(delete(RequestLink).where(RequestLink.request_id.in_(req_ids)))
        s.execute(delete(Request).where(Request.id.in_(req_ids)))
        s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids["users"])))
        s.execute(delete(User).where(User.id.in_(ids["users"])))
        s.execute(delete(Tower).where(Tower.id == ids["tower"]))
        s.execute(delete(Plan).where(Plan.id == ids["plan"]))
        s.execute(delete(Area).where(Area.id == ids["area"]))
        s.commit()


def _linked_in_october(engine, world, n: int) -> list[int]:
    with Session(engine) as s:
        made = [
            request_factory(
                s,
                s.get(User, world["users"][0]),
                status="linked",
                linked_at=OCTOBER,
                linked_by=world["users"][1],
                area=s.get(Area, world["area"]),
                tower=s.get(Tower, world["tower"]),
                plan=s.get(Plan, world["plan"]),
            )
            for _ in range(n)
        ]
        s.commit()
        return [r.id for r in made]


def _race(engine, actions) -> list[str]:
    """Run each `action(session)` in its own thread behind one barrier; the outcome codes."""
    barrier = threading.Barrier(len(actions))
    outcomes: list[str] = []
    lock = threading.Lock()

    def run(action) -> None:
        with Session(engine) as s:
            barrier.wait()
            try:
                action(s)
                result = "ok"
            except AppError as err:
                s.rollback()
                result = err.code
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=run, args=(a,)) for a in actions]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return sorted(outcomes)


def _pay_action(world, admin_index: int, count: int):
    def action(s):
        commission_service.pay(
            s,
            s.get(User, world["users"][admin_index]),
            MONTH,
            world["users"][0],
            count,
            count * 5000,
        )

    return action


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_two_admins_one_payment(engine, world, round_) -> None:
    _linked_in_october(engine, world, 2)
    outcomes = _race(engine, [_pay_action(world, 1, 2), _pay_action(world, 2, 2)])
    assert outcomes == ["already_paid", "ok"]
    with Session(engine) as s:
        payments = s.scalars(
            select(CommissionPayment).where(CommissionPayment.marketer_id == world["users"][0])
        ).all()
        assert len(payments) == 1
        audits = s.scalars(
            select(AuditLog).where(
                AuditLog.action == "commission.paid", AuditLog.actor_id.in_(world["users"])
            )
        ).all()
        assert len(audits) == 1


@pytest.mark.parametrize("round_", range(ROUNDS))
def test_a_payment_never_holds_an_undone_request(engine, world, round_) -> None:
    first, _second = _linked_in_october(engine, world, 2)
    with Session(engine) as s:
        link_id = s.scalar(
            select(RequestLink.id).where(
                RequestLink.request_id == first, RequestLink.kind == "linked"
            )
        )

    def undo(s):
        link_service.unlink(
            s, s.get(User, world["users"][1]), first, UnlinkIn(reason="by_mistake", link_id=link_id)
        )

    outcomes = _race(engine, [_pay_action(world, 2, 2), undo])
    with Session(engine) as s:
        payment = s.scalar(
            select(CommissionPayment).where(CommissionPayment.marketer_id == world["users"][0])
        )
        if outcomes == ["commission_changed", "ok"]:
            # The undo went first: the admin is told the figures changed; nothing is paid.
            assert payment is None
        else:
            # The pay went first: the undo came after it, on a paid request (an alert, FR-015).
            assert outcomes == ["ok", "ok"]
            assert payment.count == 2
            undone_at = s.scalar(
                select(RequestLink.at).where(
                    RequestLink.request_id == first, RequestLink.kind == "unlinked"
                )
            )
            assert undone_at is not None
