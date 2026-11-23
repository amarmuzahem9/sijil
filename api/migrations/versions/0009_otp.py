"""otp_challenges + drafts.otp_verified_at/otp_context_hash (feature 007)

One row per successful WhatsApp code send; the same rows serve the 60 s resend wait and the
5-per-phone-per-hour limit, so they outlive the draft (request_id SET NULL). The plain code is
never stored. See specs/007-phone-otp/data-model.md.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otp_challenges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("phone ~ '^07[0-9]{9}$'", name="otp_challenges_phone_format"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name="otp_challenges_attempts_range"),
    )
    op.create_index(
        "otp_challenges_request_created_idx",
        "otp_challenges",
        ["request_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "otp_challenges_phone_created_idx",
        "otp_challenges",
        ["phone", sa.text("created_at DESC")],
    )
    op.add_column("drafts", sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drafts", sa.Column("otp_context_hash", sa.Text(), nullable=True))
    op.create_check_constraint(
        "drafts_otp_pair",
        "drafts",
        "(otp_verified_at IS NULL) = (otp_context_hash IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("drafts_otp_pair", "drafts", type_="check")
    op.drop_column("drafts", "otp_context_hash")
    op.drop_column("drafts", "otp_verified_at")
    op.drop_index("otp_challenges_phone_created_idx", table_name="otp_challenges")
    op.drop_index("otp_challenges_request_created_idx", table_name="otp_challenges")
    op.drop_table("otp_challenges")
