"""Synthetic data for e2e/tests/commissions.spec.ts (specs/017 T052). Runs inside the throwaway
e2e api, called by scripts/e2e.sh after `seed-demo --e2e`:

    python -m tests.e2e_commission_seed

The e2e browser has no test clock and cannot reach the database, so the links of the previous
month are written here directly, like the backup e2e seed does. Idempotent; refused in
production. Synthetic names, phones and numbers only (CLAUDE.md).

Accounts (password: DEMO_MARKETER_PASSWORD, no forced change):
- 07710017001 «مسوّق عمولات تجريبي» (marketer)
- 07710017002 «أدمن عمولات تجريبي» (admin: commissions, link)
- 07710017003 «أدمن ربط تجريبي» (admin: link)

Requests of the marketer: 3 linked last month, 1 return accepted with «لا» linked last month,
2 linked this month (phones 0781700000x).
"""

import sys
from datetime import timedelta

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.core.timeutil import baghdad_month_bounds, utc_now
from app.db import get_sessionmaker
from app.models import User

MARKETER = ("مسوّق عمولات تجريبي", "07710017001", "marketer", [])
COMMISSIONS_ADMIN = ("أدمن عمولات تجريبي", "07710017002", "admin", ["link", "commissions"])
LINK_ADMIN = ("أدمن ربط تجريبي", "07710017003", "admin", ["link"])


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


def seed(db, password: str) -> int:
    from tests.helpers.requests import request_factory

    if db.scalar(select(User.id).where(User.phone == MARKETER[1])) is not None:
        print("e2e_commission_seed: already present")
        return 0
    marketer = _user(db, password, *MARKETER)
    admin = _user(db, password, *COMMISSIONS_ADMIN)
    _user(db, password, *LINK_ADMIN)

    start, _ = baghdad_month_bounds()
    last_month = start - timedelta(days=20)  # well inside the previous Baghdad month
    now = utc_now() - timedelta(minutes=5)
    rows = [
        (last_month, {}),
        (last_month + timedelta(hours=1), {}),
        (last_month + timedelta(hours=2), {}),
        (last_month + timedelta(hours=3), {"type": "return", "counts_commission": False}),
        (now, {}),
        (now + timedelta(minutes=1), {}),
    ]
    for i, (at, extra) in enumerate(rows, start=1):
        request_factory(
            db,
            marketer,
            status="linked",
            linked_at=at,
            linked_by=admin.id,
            # Submitted and accepted before the link, as in real life.
            otp_verified_at=at - timedelta(hours=2),
            submitted_at=at - timedelta(hours=2),
            approved_at=at - timedelta(hours=1),
            phone=f"0781700000{i}",
            **extra,
        )
    db.commit()
    print(f"e2e_commission_seed: {len(rows)} linked requests for 1 marketer")
    return 0


def main() -> int:
    settings = get_settings()
    if settings.app_env == "production":
        print("e2e_commission_seed: refused in production", file=sys.stderr)
        return 1
    password = settings.demo_marketer_password or ""
    if not password:
        print("e2e_commission_seed: DEMO_MARKETER_PASSWORD is not set", file=sys.stderr)
        return 1
    with get_sessionmaker()() as db:
        return seed(db, password)


if __name__ == "__main__":
    sys.exit(main())
