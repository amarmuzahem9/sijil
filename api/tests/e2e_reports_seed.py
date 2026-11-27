"""Synthetic data for e2e/tests/reports-export.spec.ts (specs/019 T044). Runs inside the throwaway
e2e api, called by scripts/e2e.sh after the other seeds:

    python -m tests.e2e_reports_seed

Idempotent; refused in production. Synthetic names, phones and numbers only (CLAUDE.md), and
synthetic card images made by tests.helpers.card_images (never a real card).

Accounts (password: DEMO_MARKETER_PASSWORD, no forced change):
- 07710019001 «أدمن تقارير تجريبي» (admin: reports)
- 07710019002 «أدمن تقارير ومراجعة تجريبي» (admin: reports, review)
- 07710019003 «أدمن عمولات تقارير تجريبي» (admin: commissions)
- 07710019004 «مسوّق تقارير تجريبي» (marketer)

Requests in tower RPT01 «برج التقارير التجريبي», all submitted now (this Baghdad month):
- T3C-990101 «رنا تقرير تجريبية», approved, with both card images;
- T3C-990102 «=تجربة تصدير» (a name that would be a formula), approved, with both card images;
- T3C-990103 «سما تقرير تجريبية», rejected, with both card images;
- T3C-990104, rejected then deleted (no name, no images).
Its own area, tower and plan codes (RPT01, RPTPLAN): no other e2e spec uses them. No linked or
pending request: they would change the counts of commissions.spec.ts and admin-review.spec.ts.
"""

import sys
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.db import get_sessionmaker
from app.models import Area, Plan, Tower, User

REPORTS_ADMIN = ("أدمن تقارير تجريبي", "07710019001", "admin", ["reports"])
REPORTS_REVIEW_ADMIN = ("أدمن تقارير ومراجعة تجريبي", "07710019002", "admin", ["reports", "review"])
COMMISSIONS_ADMIN = ("أدمن عمولات تقارير تجريبي", "07710019003", "admin", ["commissions"])
MARKETER = ("مسوّق تقارير تجريبي", "07710019004", "marketer", [])

LIVE = (
    (990101, "رنا تقرير تجريبية", "approved", "07819000001", "199019000001"),
    (990102, "=تجربة تصدير", "approved", "07819000002", "199019000002"),
    (990103, "سما تقرير تجريبية", "rejected", "07819000003", "199019000003"),
)
DELETED = 990104


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
    from tests.helpers.requests import add_images, mark_deleted, request_factory

    if db.scalar(select(User.id).where(User.phone == REPORTS_ADMIN[1])) is not None:
        print("e2e_reports_seed: already present")
        return 0
    reviewer = _user(db, password, *REPORTS_REVIEW_ADMIN)
    _user(db, password, *REPORTS_ADMIN)
    _user(db, password, *COMMISSIONS_ADMIN)
    marketer = _user(db, password, *MARKETER)
    area = Area(name="منطقة التقارير التجريبية")
    db.add(area)
    db.flush()
    tower = Tower(code="RPT01", name="برج التقارير التجريبي", area_id=area.id)
    plan = Plan(name="RPTPLAN", trial_price=20000, second_price=35000)
    db.add_all([tower, plan])
    db.flush()
    catalog = {"area": area, "tower": tower, "plan": plan}

    for number, name, status, phone, national_id in LIVE:
        extra = {"approved_at": None} if status == "rejected" else {}
        request = request_factory(
            db,
            marketer,
            **catalog,
            **extra,
            status=status,
            number=number,
            full_name=name,
            phone=phone,
            national_id=national_id,
            national_id_input=national_id,
        )
        add_images(db, request, uploads)
    deleted = request_factory(
        db,
        marketer,
        **catalog,
        status="rejected",
        approved_at=None,
        number=DELETED,
        full_name="محذوف تقرير تجريبي",
        phone="07819000009",
    )
    mark_deleted(db, deleted, reviewer)
    db.commit()
    print("e2e_reports_seed: 4 requests (1 deleted) in RPT01, 4 accounts")
    return 0


def main() -> int:
    settings = get_settings()
    if settings.app_env == "production":
        print("e2e_reports_seed: refused in production", file=sys.stderr)
        return 1
    password = settings.demo_marketer_password or ""
    if not password:
        print("e2e_reports_seed: DEMO_MARKETER_PASSWORD is not set", file=sys.stderr)
        return 1
    uploads = Path(settings.uploads_dir)
    uploads.mkdir(parents=True, exist_ok=True)
    with get_sessionmaker()() as db:
        return seed(db, password, uploads)


if __name__ == "__main__":
    sys.exit(main())
