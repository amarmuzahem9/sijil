"""Operational commands: `python -m app.cli bootstrap` and `python -m app.cli seed-demo [--e2e]`.

Passwords are never printed.
"""

import argparse
import sys

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.db import get_sessionmaker
from app.models import User
from app.services import audit_service
from app.services.auth_service import MIN_PASSWORD_LENGTH

_BOOTSTRAP_LOCK_KEY = 7_001_001


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def bootstrap(db: Session, settings: Settings) -> int:
    """Create the main admin from SUPERADMIN_* if none exists (research.md R7)."""
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK_KEY})
    existing = db.scalar(select(User.id).where(User.role == "super_admin").limit(1))
    if existing is not None:
        db.commit()  # nothing written; just releases the advisory lock
        print("bootstrap: main admin already exists; environment values ignored")
        return 0

    phone = normalize_phone(settings.superadmin_phone)
    name = (settings.superadmin_name or "").strip()
    password = settings.superadmin_password or ""
    problems = []
    if phone is None:
        problems.append("SUPERADMIN_PHONE is missing or not a valid Iraqi mobile number")
    if not 2 <= len(name) <= 100:
        problems.append("SUPERADMIN_NAME must be 2-100 characters")
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"SUPERADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters")
    if problems:
        db.rollback()
        _err("bootstrap: no main admin exists and configuration is invalid: " + "; ".join(problems))
        return 1

    user = User(
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        role="super_admin",
        permissions=[],
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    audit_service.record(
        db,
        actor_id=None,
        action="user.bootstrap_created",
        entity_type="user",
        entity_id=user.id,
        after={"name": user.name, "phone": user.phone, "role": user.role},
    )
    db.commit()
    print(f"bootstrap: main admin created for {phone}")
    return 0


# Synthetic accounts only (CLAUDE.md: never real subscriber or marketer data).
DEMO_ACCOUNTS = [("مسوّق تجريبي", "07700000001", False)]
E2E_ACCOUNTS = [("مسوّق قفل", "07700000002", False), ("مسوّق تغيير", "07700000003", True)]


def seed_demo(db: Session, settings: Settings, e2e: bool = False) -> int:
    """Idempotently create synthetic marketers for testing (research.md R8). Never in production."""
    if settings.app_env == "production":
        _err("seed-demo: refused in production")
        return 1
    password = settings.demo_marketer_password or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        _err(f"seed-demo: DEMO_MARKETER_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters")
        return 1

    accounts = DEMO_ACCOUNTS + (E2E_ACCOUNTS if e2e else [])
    created = 0
    for name, phone, must_change in accounts:
        if db.scalar(select(User.id).where(User.phone == phone)) is not None:
            continue
        db.add(
            User(
                name=name,
                phone=phone,
                password_hash=hash_password(password),
                role="marketer",
                permissions=[],
                must_change_password=must_change,
            )
        )
        created += 1
    db.commit()
    print(f"seed-demo: {created} account(s) created, {len(accounts) - created} already present")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="create the main admin from SUPERADMIN_* if none exists")
    seed = sub.add_parser("seed-demo", help="create synthetic test marketers (not in production)")
    seed.add_argument("--e2e", action="store_true", help="also create the e2e test accounts")
    args = parser.parse_args(argv)

    settings = get_settings()
    with get_sessionmaker()() as db:
        if args.command == "bootstrap":
            return bootstrap(db, settings)
        return seed_demo(db, settings, e2e=args.e2e)


if __name__ == "__main__":
    sys.exit(main())
