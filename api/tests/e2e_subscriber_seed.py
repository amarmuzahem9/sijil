"""Synthetic data for e2e/tests/subscriber-file.spec.ts (specs/018 T035). Runs inside the throwaway
e2e api, called by scripts/e2e.sh after the other seeds:

    python -m tests.e2e_subscriber_seed

Idempotent; refused in production. Synthetic names, phones and numbers only (CLAUDE.md), and
synthetic card images made by tests.helpers.card_images (never a real card).

Accounts (password: DEMO_MARKETER_PASSWORD, no forced change):
- 07710018001 «أدمن مراجعة مشتركين تجريبي» (admin: review)
- 07710018002 «أدمن ربط مشتركين تجريبي» (admin: link)
- 07710018003 «مسوّق مشتركين تجريبي» (marketer)

Records:
- request T3C-990017 «سجى ملف تجريبية», phone 07818000001, national ID 199018000001, family
  1990E1800000000001, accepted, with its two card images;
- request T3C-990019, rejected, of another person with the same phone («نفس الهاتف»);
- legacy subscriber with the same family number («نفس العائلة»);
- request T3C-990018 with phone 07818000009, deleted.

No SAS row: sas-import.spec.ts counts every stored SAS row missing from its re-import file, so a
seeded one would change its numbers. SAS search and files are covered by the api tests.
Its own area, tower and plan codes (SFL01, SFLPLAN): no other e2e spec uses them.
"""

import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.db import get_sessionmaker
from app.models import Area, Plan, Tower, User

REVIEW_ADMIN = ("أدمن مراجعة مشتركين تجريبي", "07710018001", "admin", ["review"])
LINK_ADMIN = ("أدمن ربط مشتركين تجريبي", "07710018002", "admin", ["link"])
MARKETER = ("مسوّق مشتركين تجريبي", "07710018003", "marketer", [])
PHONE = "07818000001"
NATIONAL_ID = "199018000001"
FAMILY = "1990E1800000000001"


def _user(db, password: str, name: str, phone: str, role: str, permissions: list[str]) -> User:
    user = User(
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        permissions=permissions,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    return user


def seed(db, password: str, uploads: Path) -> int:
    from tests.helpers.legacy import legacy_subscriber
    from tests.helpers.requests import add_images, mark_deleted, request_factory

    if db.scalar(select(User.id).where(User.phone == REVIEW_ADMIN[1])) is not None:
        print("e2e_subscriber_seed: already present")
        return 0
    reviewer = _user(db, password, *REVIEW_ADMIN)
    _user(db, password, *LINK_ADMIN)
    marketer = _user(db, password, *MARKETER)
    # Its own area, tower and plan: the factory's default names restart in every process and the
    # 017 seed already used them; submit.spec.ts owns SUB01/SUBPLAN.
    area = Area(name="منطقة ملف المشترك التجريبية")
    db.add(area)
    db.flush()
    tower = Tower(code="SFL01", name="برج ملف المشترك", area_id=area.id)
    plan = Plan(name="SFLPLAN", trial_price=20000, second_price=35000)
    db.add_all([tower, plan])
    db.flush()
    catalog = {"area": area, "tower": tower, "plan": plan}

    request = request_factory(
        db,
        marketer,
        **catalog,
        status="approved",
        number=990017,
        full_name="سجى ملف تجريبية",
        phone=PHONE,
        national_id=NATIONAL_ID,
        national_id_input=NATIONAL_ID,
        family_number=FAMILY,
    )
    add_images(db, request, uploads)
    request_factory(
        db,
        marketer,
        **catalog,
        status="rejected",
        approved_at=None,
        number=990019,
        full_name="سجى هاتف مرفوضة",
        phone=PHONE,
    )
    legacy_subscriber(db, reviewer, family_number=FAMILY, full_name="سجى ملف قديمة")
    deleted = request_factory(
        db,
        marketer,
        **catalog,
        status="pending_review",
        approved_at=None,
        number=990018,
        phone="07818000009",
    )
    mark_deleted(db, deleted, reviewer)
    db.commit()
    print("e2e_subscriber_seed: 3 requests (1 rejected, 1 deleted), 1 legacy, 3 accounts")
    return 0


def main() -> int:
    settings = get_settings()
    if settings.app_env == "production":
        print("e2e_subscriber_seed: refused in production", file=sys.stderr)
        return 1
    password = settings.demo_marketer_password or ""
    if not password:
        print("e2e_subscriber_seed: DEMO_MARKETER_PASSWORD is not set", file=sys.stderr)
        return 1
    uploads = Path(settings.uploads_dir)
    uploads.mkdir(parents=True, exist_ok=True)
    with get_sessionmaker()() as db:
        return seed(db, password, uploads)


if __name__ == "__main__":
    sys.exit(main())
