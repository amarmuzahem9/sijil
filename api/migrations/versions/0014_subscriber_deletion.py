"""Subscriber deletion: erase a pending or rejected request in place (specs/011 data-model.md).

- requests: the deletion mark (deleted_at, deleted_by, deletion_reason); the personal columns made
  nullable; `requests_erasure` ties them to the mark (a live row keeps them, a marked row holds
  none); the surname and rejection-note checks apply to live rows only; the pending index leaves
  deleted rows out (constitution III v1.3.0, system.md v1.15 §7.4).
- users: the permission `delete`.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

DELETION_REASONS = ("duplicate", "test", "entry_error", "other")

# Required on a live row today; nullable from 0014 so a deletion can erase them.
MADE_NULLABLE = (
    "first_name",
    "father_name",
    "grandfather_name",
    "great_grandfather_name",
    "full_name",
    "mother_first_name",
    "mother_second_name",
    "no_surname",
    "national_id",
    "national_id_input",
    "submitted_national_id",
    "family_number",
    "submitted_family_number",
    "family_key",
    "birth_date",
    "issue_date",
    "expiry_date",
    "birth_place",
    "issuing_authority",
    "card_fields",
    "card_readings",
    "location_lat",
    "location_lng",
    "location_source",
    "address",
    "landmark",
    "phone",
    "username",
)
# Already nullable, and erased too.
ALSO_ERASED = (
    "surname",
    "mother_third_name",
    "mother_surname",
    "national_id_check",
    "location_accuracy_m",
    "rejection_note",
)

KNOWN_BEFORE = '["review", "link", "settings", "marketers", "reports", "commissions"]'
KNOWN_AFTER = '["review", "link", "settings", "marketers", "reports", "commissions", "delete"]'

NO_SURNAME = "NOT no_surname OR surname IS NULL"
SURNAME_REQUIRED = "no_surname OR surname IS NOT NULL"
REJECTION_NOTE = (
    "CASE WHEN rejection_reason = 'other' "
    "THEN rejection_note IS NOT NULL AND btrim(rejection_note) <> '' "
    "ELSE rejection_note IS NULL END"
)


def _erasure_check() -> str:
    live = " AND ".join(f"{c} IS NOT NULL" for c in MADE_NULLABLE)
    erased = " AND ".join(f"{c} IS NULL" for c in MADE_NULLABLE + ALSO_ERASED)
    return f"CASE WHEN deleted_at IS NULL THEN {live} ELSE {erased} END"


def _replace_check(name: str, condition: str) -> None:
    op.drop_constraint(name, "requests", type_="check")
    op.create_check_constraint(name, "requests", condition)


def upgrade() -> None:
    # --- requests: the mark ---
    op.add_column("requests", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "requests",
        sa.Column("deleted_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("requests", sa.Column("deletion_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "requests_deletion_mark",
        "requests",
        "(deleted_at IS NULL) = (deleted_by IS NULL) "
        "AND (deleted_at IS NULL) = (deletion_reason IS NULL)",
    )
    codes = ",".join(f"'{c}'" for c in DELETION_REASONS)
    op.create_check_constraint(
        "requests_deletion_reason",
        "requests",
        f"deletion_reason IS NULL OR deletion_reason IN ({codes})",
    )
    op.create_check_constraint(
        "requests_deletable_status",
        "requests",
        "deleted_at IS NULL OR status IN ('pending_review','rejected')",
    )

    # --- requests: the erasable columns ---
    for column in MADE_NULLABLE:
        op.alter_column("requests", column, nullable=True)
    op.create_check_constraint("requests_erasure", "requests", _erasure_check())
    _replace_check("requests_no_surname", f"deleted_at IS NOT NULL OR ({NO_SURNAME})")
    _replace_check("requests_surname_required", f"deleted_at IS NOT NULL OR ({SURNAME_REQUIRED})")
    _replace_check("requests_rejection_note", f"deleted_at IS NOT NULL OR ({REJECTION_NOTE})")

    op.drop_index("requests_pending_idx", table_name="requests")
    op.create_index(
        "requests_pending_idx",
        "requests",
        ["submitted_at"],
        postgresql_where=sa.text("status = 'pending_review' AND deleted_at IS NULL"),
    )

    # --- users ---
    op.drop_constraint("users_permissions_known", "users", type_="check")
    op.create_check_constraint(
        "users_permissions_known", "users", f"permissions <@ '{KNOWN_AFTER}'::jsonb"
    )


def downgrade() -> None:
    # Erased data cannot come back, so the columns cannot be required again; and an admin would
    # lose a permission silently. Refuse instead.
    blocked = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT count(*) FROM requests WHERE deleted_at IS NOT NULL) "
                "+ (SELECT count(*) FROM users WHERE permissions @> '[\"delete\"]')"
            )
        )
        .scalar_one()
    )
    if blocked:
        raise RuntimeError("0014 downgrade refused: deleted requests or `delete` holders exist")

    op.drop_constraint("users_permissions_known", "users", type_="check")
    op.create_check_constraint(
        "users_permissions_known", "users", f"permissions <@ '{KNOWN_BEFORE}'::jsonb"
    )

    op.drop_index("requests_pending_idx", table_name="requests")
    op.create_index(
        "requests_pending_idx",
        "requests",
        ["submitted_at"],
        postgresql_where=sa.text("status = 'pending_review'"),
    )
    _replace_check("requests_rejection_note", REJECTION_NOTE)
    _replace_check("requests_surname_required", SURNAME_REQUIRED)
    _replace_check("requests_no_surname", NO_SURNAME)
    op.drop_constraint("requests_erasure", "requests", type_="check")
    for column in MADE_NULLABLE:
        op.alter_column("requests", column, nullable=False)

    for name in ("requests_deletable_status", "requests_deletion_reason", "requests_deletion_mark"):
        op.drop_constraint(name, "requests", type_="check")
    for column in ("deletion_reason", "deleted_by", "deleted_at"):
        op.drop_column("requests", column)
