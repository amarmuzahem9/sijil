"""permissions CHECK + audit actor index (feature 002)

See specs/002-accounts-permissions/data-model.md

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

KNOWN = '["review", "link", "settings", "marketers", "reports", "commissions"]'


def upgrade() -> None:
    op.create_check_constraint(
        "users_permissions_known", "users", f"permissions <@ '{KNOWN}'::jsonb"
    )
    op.execute("CREATE INDEX audit_log_actor_created_idx ON audit_log (actor_id, created_at DESC)")


def downgrade() -> None:
    op.drop_index("audit_log_actor_created_idx", table_name="audit_log")
    op.drop_constraint("users_permissions_known", "users", type_="check")
