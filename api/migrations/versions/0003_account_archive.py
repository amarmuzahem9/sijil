"""account archive (feature 003)

See specs/003-account-archive/data-model.md

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

OLD_REASONS = "'logout', 'password_changed', 'password_reset', 'deactivated', 'reuse_detected'"
NEW_REASONS = OLD_REASONS + ", 'archived'"


def upgrade() -> None:
    op.add_column("users", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("archived_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_check_constraint(
        "users_archive_pair", "users", "(archived_at IS NULL) = (archived_by IS NULL)"
    )
    op.create_check_constraint(
        "users_archived_inactive", "users", "archived_at IS NULL OR is_active = false"
    )
    op.create_check_constraint(
        "users_super_admin_not_archived", "users", "role <> 'super_admin' OR archived_at IS NULL"
    )
    op.drop_constraint("sessions_revoke_reason_valid", "sessions", type_="check")
    op.create_check_constraint(
        "sessions_revoke_reason_valid",
        "sessions",
        f"revoke_reason IS NULL OR revoke_reason IN ({NEW_REASONS})",
    )


def downgrade() -> None:
    op.execute("UPDATE sessions SET revoke_reason = 'deactivated' WHERE revoke_reason = 'archived'")
    op.drop_constraint("sessions_revoke_reason_valid", "sessions", type_="check")
    op.create_check_constraint(
        "sessions_revoke_reason_valid",
        "sessions",
        f"revoke_reason IS NULL OR revoke_reason IN ({OLD_REASONS})",
    )
    op.drop_constraint("users_super_admin_not_archived", "users", type_="check")
    op.drop_constraint("users_archived_inactive", "users", type_="check")
    op.drop_constraint("users_archive_pair", "users", type_="check")
    op.drop_column("users", "archived_by")
    op.drop_column("users", "archived_at")
