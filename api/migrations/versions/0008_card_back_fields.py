"""drafts: the other fields on the back of the card (feature 006, owner change; system.md v1.8)

Date of birth, place of birth, issue date, expiry date and issuing authority. All nullable on a
draft (they are required only for sending). See specs/006-card-ocr/data-model.md.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TEXT_MAX = 100


def upgrade() -> None:
    op.add_column("drafts", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("drafts", sa.Column("birth_place", sa.Text(), nullable=True))
    op.add_column("drafts", sa.Column("issue_date", sa.Date(), nullable=True))
    op.add_column("drafts", sa.Column("expiry_date", sa.Date(), nullable=True))
    op.add_column("drafts", sa.Column("issuing_authority", sa.Text(), nullable=True))
    op.create_check_constraint(
        "drafts_birth_place_length",
        "drafts",
        f"birth_place IS NULL OR char_length(birth_place) <= {TEXT_MAX}",
    )
    op.create_check_constraint(
        "drafts_issuing_authority_length",
        "drafts",
        f"issuing_authority IS NULL OR char_length(issuing_authority) <= {TEXT_MAX}",
    )


def downgrade() -> None:
    op.drop_constraint("drafts_issuing_authority_length", "drafts", type_="check")
    op.drop_constraint("drafts_birth_place_length", "drafts", type_="check")
    for column in ("issuing_authority", "expiry_date", "issue_date", "birth_place", "birth_date"):
        op.drop_column("drafts", column)
