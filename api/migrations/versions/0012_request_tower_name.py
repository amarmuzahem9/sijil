"""The tower name is copied on drafts and fixed on requests (system.md v1.12 §5).

Requests submitted before this migration take the tower's current name: it is the best value
available, and towers can only be renamed through the audited settings page.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drafts", sa.Column("tower_name", sa.Text(), nullable=True))
    op.execute(
        "UPDATE drafts d SET tower_name = t.name FROM towers t "
        "WHERE d.tower_id = t.id AND d.tower_code IS NOT NULL"
    )
    op.add_column("requests", sa.Column("tower_name", sa.Text(), nullable=True))
    op.execute("UPDATE requests r SET tower_name = t.name FROM towers t WHERE r.tower_id = t.id")
    op.alter_column("requests", "tower_name", nullable=False)


def downgrade() -> None:
    op.drop_column("requests", "tower_name")
    op.drop_column("drafts", "tower_name")
