"""card reading: card_readings, drafts provenance columns, image_access_log.purpose (feature 006)

See specs/006-card-ocr/data-model.md

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

STATES = ("pending", "running", "done", "reshoot", "failed")
RESHOOT_REASONS = ("no_card", "wrong_side", "not_unified", "multiple")
FAILED_REASONS = ("timeout", "unavailable", "error")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # drafts: provenance of the card fields, the no-surname choice, the national-ID check.
    op.add_column(
        "drafts",
        sa.Column(
            "card_fields",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "drafts",
        sa.Column("no_surname", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("drafts", sa.Column("national_id_check", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "drafts_no_surname_empty", "drafts", "NOT no_surname OR surname IS NULL"
    )

    # image_access_log: who/what opened the image (analysis C1, Principle II).
    op.add_column(
        "image_access_log",
        sa.Column("purpose", sa.Text(), nullable=False, server_default=sa.text("'view'")),
    )
    op.create_check_constraint(
        "image_access_log_purpose", "image_access_log", "purpose IN ('view', 'ocr')"
    )

    op.create_table(
        "card_readings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("image_file_name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("queued_by_client", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("draft_id", "side", name="card_readings_draft_side_key"),
        sa.CheckConstraint("side IN ('front', 'back')", name="card_readings_side"),
        sa.CheckConstraint(f"state IN ({_in(STATES)})", name="card_readings_state"),
        sa.CheckConstraint(
            f"(state = 'reshoot' AND reason IN ({_in(RESHOOT_REASONS)}))"
            f" OR (state = 'failed' AND reason IN ({_in(FAILED_REASONS)}))"
            " OR (state NOT IN ('reshoot', 'failed') AND reason IS NULL)",
            name="card_readings_reason",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="card_readings_duration"
        ),
    )
    op.create_index(
        "card_readings_running_idx",
        "card_readings",
        ["started_at"],
        postgresql_where=sa.text("state = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("card_readings_running_idx", table_name="card_readings")
    op.drop_table("card_readings")
    op.drop_constraint("image_access_log_purpose", "image_access_log", type_="check")
    op.drop_column("image_access_log", "purpose")
    op.drop_constraint("drafts_no_surname_empty", "drafts", type_="check")
    op.drop_column("drafts", "national_id_check")
    op.drop_column("drafts", "no_surname")
    op.drop_column("drafts", "card_fields")
