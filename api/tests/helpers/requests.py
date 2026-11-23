"""Synthetic submitted requests for tests (specs/008 tasks T002).

A factory request is an "existing subscriber" for the check engine. Every value is made up; no
real card, name or number. Rejected rows also come from here until feature 010 adds a screen.
"""

import itertools
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.family_key import family_key
from app.core.timeutil import utc_now
from app.models import Area, Plan, Request, Tower, User

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


def request_factory(db: Session, marketer: User, **overrides: Any) -> Request:
    """Insert a valid request. `status` defaults to approved; any field may be overridden.
    `family_key` follows `family_number` unless given."""
    import uuid

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
    request = Request(**values)
    db.add(request)
    db.flush()
    return request
