"""Requests exports (specs/019 data-model.md).

`exports` holds one row per «تصدير» of «التقارير والتصدير» (ids, codes and counts only, never
subscriber data), with one `preparing` row per admin at most. `image_access_log.purpose` gains
`export`: every card image sent in a download is logged like any open (analysis C1, Principle II).
`requests_submitted_at_idx` serves the submission-date filter (research R3).

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filters", JSONB(), nullable=False),
        sa.Column("include_identity", sa.Boolean(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("missing_images", sa.Integer()),
        sa.Column("error_code", sa.Text()),
        sa.Column("ticket_hash", sa.Text()),
        sa.Column("ticket_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "state IN ('preparing','ready','failed','removed')", name="exports_state"
        ),
        sa.CheckConstraint(
            "(state = 'ready') = "
            "(ready_at IS NOT NULL AND expires_at IS NOT NULL AND removed_at IS NULL)",
            name="exports_ready_times",
        ),
    )
    op.create_index(
        "exports_one_preparing",
        "exports",
        ["requester_id"],
        unique=True,
        postgresql_where=sa.text("state = 'preparing'"),
    )
    op.create_index(
        "exports_requester_created", "exports", ["requester_id", sa.text("created_at DESC")]
    )
    op.create_index(
        "requests_submitted_at_idx",
        "requests",
        [sa.text("submitted_at DESC"), sa.text("id DESC")],
    )
    op.drop_constraint("image_access_log_purpose", "image_access_log", type_="check")
    op.create_check_constraint(
        "image_access_log_purpose", "image_access_log", "purpose IN ('view', 'ocr', 'export')"
    )


def downgrade() -> None:
    # Access rows are never deleted (Principle II): refuse rather than drop `export` rows.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM image_access_log WHERE purpose = 'export') THEN
            RAISE EXCEPTION 'image_access_log has export rows; 0021 cannot be downgraded';
          END IF;
        END $$;
        """
    )
    op.drop_constraint("image_access_log_purpose", "image_access_log", type_="check")
    op.create_check_constraint(
        "image_access_log_purpose", "image_access_log", "purpose IN ('view', 'ocr')"
    )
    op.drop_index("requests_submitted_at_idx", table_name="requests")
    op.drop_index("exports_requester_created", table_name="exports")
    op.drop_index("exports_one_preparing", table_name="exports")
    op.drop_table("exports")
