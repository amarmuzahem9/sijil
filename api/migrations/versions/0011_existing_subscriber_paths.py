"""Existing subscriber paths (specs/009 data-model.md): drafts.return_key, reason numbers_conflict.

Revision ID: 0011
Revises: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_OLD = "reason IN ('family_exists','numbers_edited','return')"
_NEW = "reason IN ('family_exists','numbers_edited','return','numbers_conflict')"


def upgrade() -> None:
    op.add_column("drafts", sa.Column("return_key", sa.Text(), nullable=True))
    op.drop_constraint("request_reasons_reason", "request_reasons", type_="check")
    op.create_check_constraint("request_reasons_reason", "request_reasons", _NEW)


def downgrade() -> None:
    op.execute("DELETE FROM request_reasons WHERE reason = 'numbers_conflict'")
    op.drop_constraint("request_reasons_reason", "request_reasons", type_="check")
    op.create_check_constraint("request_reasons_reason", "request_reasons", _OLD)
    op.drop_column("drafts", "return_key")
