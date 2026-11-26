"""Synthetic submitted requests for tests (specs/008 tasks T002).

A factory request is an "existing subscriber" for the check engine. Every value is made up; no
real card, name or number. Rejected rows also come from here until feature 010 adds a screen.
"""

import itertools
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.family_key import family_key
from app.core.timeutil import utc_now
from app.models import (
    Area,
    Plan,
    Request,
    RequestImage,
    RequestLink,
    RequestNumberPin,
    Tower,
    User,
)
from app.models.otp import OtpChallenge

_counter = itertools.count(1)


def _catalog(db: Session) -> tuple[Area, Tower, Plan]:
    n = next(_counter)
    area = Area(name=f"منطقة اختبار {n}")
    db.add(area)
    db.flush()
    tower = Tower(code=f"TST{n:02d}", name=f"برج اختبار {n}", area_id=area.id)
    plan = Plan(name=f"PLAN{n}", trial_price=20000, second_price=35000)
    db.add_all([tower, plan])
    db.flush()
    return area, tower, plan


def _link_admin(db: Session) -> User:
    """A synthetic main admin who "linked" factory rows (specs/013 tasks T010)."""
    n = next(_counter)
    admin = User(
        name=f"أدمن الربط {n}",
        phone=f"0776{n:07d}",  # not make_user's 0771000…
        password_hash="synthetic",
        role="super_admin",
        permissions=[],
    )
    db.add(admin)
    db.flush()
    return admin


def request_factory(db: Session, marketer: User, **overrides: Any) -> Request:
    """Insert a valid request. `status` defaults to approved; any field may be overridden.
    `family_key` follows `family_number` unless given. A `linked` row gets `linked_at`,
    `linked_by` and its `request_links` row, so it has a current `link_id` (specs/013)."""
    area, tower, plan = (
        (overrides.pop("area"), overrides.pop("tower"), overrides.pop("plan"))
        if "tower" in overrides
        else _catalog(db)
    )
    n = next(_counter)
    now = utc_now()
    status = overrides.get("status", "approved")
    phone = overrides.get("phone", f"0790000{n:04d}")
    family_number = overrides.get("family_number", f"1000A{n:013d}")
    values: dict[str, Any] = {
        "number": db.execute(text("SELECT nextval('request_number_seq')")).scalar_one(),
        "draft_id": uuid.uuid4(),
        "marketer_id": marketer.id,
        "type": "new",
        "status": status,
        "first_name": "تجربة",
        "father_name": "اختبار",
        "grandfather_name": "نموذج",
        "great_grandfather_name": "مثال",
        "surname": "التجريبي",
        "mother_first_name": "عينة",
        "mother_second_name": "نموذجية",
        "full_name": "تجربة اختبار نموذج مثال التجريبي",
        "no_surname": False,
        "national_id": f"1990{n:08d}",
        "national_id_input": f"1990{n:08d}",
        "family_number": family_number,
        "birth_date": now.date().replace(year=1990),
        "issue_date": now.date().replace(year=2020),
        "expiry_date": now.date().replace(year=2030),
        "birth_place": "بغداد",
        "issuing_authority": "مديرية الجنسية والمعلومات المدنية",
        "card_fields": {},
        "card_readings": {"front": None, "back": None},
        "location_lat": 34.7,
        "location_lng": 43.68,
        "location_source": "gps",
        "address": "حي تجريبي",
        "landmark": "قرب نقطة تجريبية",
        "area_id": area.id,
        "tower_id": tower.id,
        "plan_id": plan.id,
        "area_name": area.name,
        "tower_code": tower.code,
        "tower_name": tower.name,
        "plan_name": plan.name,
        "trial_price": plan.trial_price,
        "second_price": plan.second_price,
        "phone": phone,
        "username": f"{tower.code}-{phone}",
        "otp_verified_at": now,
        "submitted_at": now,
        "approved_at": now if status in ("approved", "linked") else None,
    }
    values.update(overrides)
    if "family_key" not in overrides:
        values["family_key"] = family_key(values["family_number"])
    values.setdefault("submitted_national_id", values["national_id_input"])
    values.setdefault("submitted_family_number", values["family_number"])
    if values["status"] == "rejected":
        # The 010 decision columns a rejected request must carry (specs/010 data-model.md).
        values.setdefault("rejected_at", now)
        values.setdefault("rejected_by", marketer.id)
        values.setdefault("rejection_reason", "card_unclear")
    if values["status"] == "linked":
        values.setdefault("linked_at", now)
        if "linked_by" not in values:
            values["linked_by"] = _link_admin(db).id
    request = Request(**values)
    db.add(request)
    db.flush()
    if request.status == "linked":
        db.add(
            RequestLink(
                request_id=request.id,
                kind="linked",
                actor_id=request.linked_by,
                at=request.linked_at,
            )
        )
        db.flush()
    return request


def link_request(db: Session, request: Request, admin: User, at=None) -> RequestLink:
    """Link an approved request directly, without the service: status, current link and its
    history row (specs/013 data-model.md)."""
    when = at or utc_now()
    request.status = "linked"
    request.linked_at = when
    request.linked_by = admin.id
    row = RequestLink(request_id=request.id, kind="linked", actor_id=admin.id, at=when)
    db.add(row)
    db.flush()
    return row


def pay_month(
    db: Session,
    marketer: User,
    month,
    admin: User,
    requests: list[Request],
    rate: int = 5000,
    tier_min_count: int = 0,
    at=None,
):
    """A «تم الدفع» written directly (specs/017 data-model.md), for tests that need a paid month
    of exactly `requests`."""
    from app.models import CommissionPayment, CommissionPaymentRequest

    payment = CommissionPayment(
        marketer_id=marketer.id,
        month=month,
        count=len(requests),
        tier_min_count=tier_min_count,
        rate=rate,
        amount=rate * len(requests),
        paid_by=admin.id,
        paid_at=at or utc_now(),
    )
    db.add(payment)
    db.flush()
    db.add_all(CommissionPaymentRequest(request_id=r.id, payment_id=payment.id) for r in requests)
    db.flush()
    return payment


# --- extras for deletion tests (specs/011 tasks T014) ---------------------------------------------


def add_images(db: Session, request: Request, uploads: Path) -> list[RequestImage]:
    """Front and back synthetic image files in `uploads`, with their `request_images` rows."""
    from tests.helpers.card_images import scenario_jpeg

    images = []
    for side in ("front", "back"):
        name = f"{uuid.uuid4().hex}.jpg"
        (uploads / name).write_bytes(scenario_jpeg("clear_front", 120, 76))
        images.append(
            RequestImage(
                id=uuid.uuid4(),
                request_id=request.id,
                side=side,
                file_name=name,
                size_bytes=1000,
                width=120,
                height=76,
                uploaded_by=request.marketer_id,
                created_at=utc_now(),
            )
        )
    db.add_all(images)
    db.flush()
    return images


def add_pin(db: Session, request: Request, admin: User) -> RequestNumberPin:
    """One national-ID pin with made-up values before and after."""
    pin = RequestNumberPin(
        request_id=request.id,
        field="national_id",
        previous_value=request.national_id,
        value="199000000099",
        source="typed",
        pinned_by=admin.id,
        pinned_at=utc_now(),
    )
    db.add(pin)
    db.flush()
    return pin


def add_otp_rows(
    db: Session, phone: str, count: int, *, draft_id: uuid.UUID | None = None
) -> list[OtpChallenge]:
    """`count` OTP rows for `phone` sent in the last hour; `draft_id` None = a submitted draft."""
    now = utc_now()
    rows = [
        OtpChallenge(
            id=uuid.uuid4(),
            request_id=draft_id,
            phone=phone,
            code_hash="synthetic",
            context_hash="synthetic",
            expires_at=now + timedelta(minutes=5),
            created_at=now - timedelta(minutes=count - i),
        )
        for i in range(count)
    ]
    db.add_all(rows)
    db.flush()
    return rows


def mark_deleted(db: Session, request: Request, admin: User, reason: str = "test") -> Request:
    """The deleted state written directly (data-model.md › requests), without the service: for
    tests of the paths around a deleted request."""
    from app.models.request import ERASED_COLUMNS

    for column in ERASED_COLUMNS:
        setattr(request, column, None)
    request.deleted_at = utc_now()
    request.deleted_by = admin.id
    request.deletion_reason = reason
    db.flush()
    return request
