"""Legacy subscriber test helpers (specs/014). Synthetic values only."""

import itertools
from typing import Any

from sqlalchemy.orm import Session

from app.core.family_key import family_key
from app.core.legacy_row import counts_in_check
from app.models import LegacyImport, LegacySubscriber, User

_numbers = itertools.count(500)


def legacy_subscriber(db: Session, admin: User, **values: Any) -> LegacySubscriber:
    """One imported legacy subscriber, in its own import. `family_number` sets the key and
    `status_text` sets `counts_in_check`, as a real import would."""
    imp = LegacyImport(
        created_by=admin.id,
        file_name="legacy_test.csv",
        rows_total=1,
        imported=1,
        skipped=0,
        already_imported=0,
        not_counted=0,
        incomplete=0,
        corrected=0,
    )
    db.add(imp)
    db.flush()
    family = values.pop("family_number", None)
    status = values.pop("status_text", "تم")
    row = {
        "legacy_number": f"T3C-{next(_numbers) % 1000:03d}",
        "full_name": "مشترك قديم تجريبي",
        "first_name": "مشترك",
        "family_number_file": family,
        "family_number": family,
        "family_key": family_key(family),
        "status_text": status,
        "counts_in_check": counts_in_check(status),
        "incomplete": False,
        "extra": {},
    } | values
    sub = LegacySubscriber(import_id=imp.id, **row)
    db.add(sub)
    db.flush()
    return sub
