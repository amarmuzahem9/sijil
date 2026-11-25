"""Synthetic data for scripts/backup-e2e.sh (specs/016 T033). Runs inside the throwaway e2e api.

python -m tests.e2e_backup_seed seed     admin, marketer, 3 requests with images, legacy, SAS
python -m tests.e2e_backup_seed mutate   one more request; one request erased (rows + files)
python -m tests.e2e_backup_seed bulk MB  MB of random bytes in image-named files (SC-003 timing)
"""

import sys
from pathlib import Path

from sqlalchemy import delete, select

from app.config import get_settings
from app.core.timeutil import utc_now
from app.db import get_sessionmaker
from app.models import Area, LegacyImage, Plan, Request, RequestImage, Tower, User


def _user(db, role: str, phone: str) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(name=f"مستخدم تجربة {phone[-3:]}", phone=phone, password_hash="x", role=role)
        user.permissions = []
        db.add(user)
        db.flush()
    return user


def seed(db, uploads: Path) -> None:
    from tests.helpers.backup import new_image_name
    from tests.helpers.card_images import scenario_jpeg
    from tests.helpers.legacy import legacy_subscriber
    from tests.helpers.requests import add_images, request_factory
    from tests.helpers.sas import sas_subscriber

    admin = _user(db, "super_admin", "07710008001")
    marketer = _user(db, "marketer", "07710008002")
    for status in ("approved", "approved", "pending_review"):
        add_images(db, request_factory(db, marketer, status=status), uploads)
    legacy = legacy_subscriber(db, admin, family_number="E2E0000000000000001")
    name = new_image_name()
    (uploads / name).write_bytes(scenario_jpeg("clear_front", 90, 60))
    db.add(
        LegacyImage(
            legacy_subscriber_id=legacy.id,
            side="front",
            file_name=name,
            size_bytes=100,
            width=90,
            height=60,
            created_at=utc_now(),
        )
    )
    sas_subscriber(db, admin, username="ZZT01-07700000456")


def mutate(db, uploads: Path) -> None:
    from tests.helpers.requests import add_images, mark_deleted, request_factory

    admin = db.scalar(select(User).where(User.role == "super_admin"))
    marketer = db.scalar(select(User).where(User.role == "marketer"))
    # A new process restarts the factory's counters: reuse the catalog of an existing request.
    first = db.scalar(select(Request).order_by(Request.id))
    catalog = {
        "area": db.get(Area, first.area_id),
        "tower": db.get(Tower, first.tower_id),
        "plan": db.get(Plan, first.plan_id),
    }
    unique = {
        "phone": "07900009999",
        "national_id": "199099999999",
        "national_id_input": "199099999999",
        "family_number": "1000A9999999999999",
    }
    add_images(db, request_factory(db, marketer, **catalog, **unique), uploads)
    # Only a pending or rejected request can be erased (specs/011).
    victim = db.scalar(select(Request).where(Request.status == "pending_review"))
    names = [i.file_name for i in victim.images]
    db.execute(delete(RequestImage).where(RequestImage.request_id == victim.id))
    mark_deleted(db, victim, admin)
    db.commit()
    for name in names:
        (uploads / name).unlink(missing_ok=True)


def bulk(uploads: Path, megabytes: int) -> None:
    """Random bytes, not images: the backup and restore treat every stored file alike."""
    import os
    import uuid

    for _ in range(megabytes * 1024 // 400):
        (uploads / f"{uuid.uuid4().hex}.jpg").write_bytes(os.urandom(400 * 1024))


def main() -> int:
    uploads = Path(get_settings().uploads_dir)
    if sys.argv[1] == "bulk":
        bulk(uploads, int(sys.argv[2]))
        return 0
    with get_sessionmaker()() as db:
        {"seed": seed, "mutate": mutate}[sys.argv[1]](db, uploads)
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
