"""Backup mirror tables (specs/016 data-model.md «Tables (mirror)», research R8).

The backup files in BACKUP_DIR are the source of truth; these tables only mirror them for the
main admin's «النسخ الاحتياطي» page and the home warnings, and are rebuilt from the files by the
`backup` service. `backup_runs` (one snapshot or manual request), `backup_events` (drills, external
copies, restores, deploys), `backup_status` (one row: heartbeat and disk space). No personal data.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_KINDS = "('nightly', 'manual', 'pre_deploy', 'pre_restore')"
_STATUSES = "('requested', 'running', 'succeeded', 'failed', 'removed')"
_ERRORS = (
    "('disk_low', 'missing_images', 'dump_failed', 'encrypt_failed', 'verify_failed', "
    "'busy', 'internal')"
)


def _tsz(name: str, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("snapshot_id", sa.Text(), nullable=True, unique=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column(
            "requested_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        _tsz("started_at"),
        _tsz("finished_at"),
        sa.Column("total_size", sa.BigInteger(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("counts", JSONB(), nullable=True),
        _tsz("removed_at"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"kind IN {_KINDS}", name="backup_runs_kind"),
        sa.CheckConstraint(f"status IN {_STATUSES}", name="backup_runs_status"),
        sa.CheckConstraint(
            f"error_code IS NULL OR error_code IN {_ERRORS}", name="backup_runs_error_code"
        ),
    )
    # One operation at a time (research R5): at most one run requested or running.
    op.create_index(
        "backup_runs_one_active",
        "backup_runs",
        [sa.text("(true)")],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'running')"),
    )
    op.create_index("backup_runs_created", "backup_runs", ["created_at"])

    op.create_table(
        "backup_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        _tsz("at", nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            "type IN ('drill', 'external_copy', 'restore', 'deploy')", name="backup_events_type"
        ),
        sa.CheckConstraint(
            "result IN ('passed', 'failed', 'succeeded')", name="backup_events_result"
        ),
    )
    op.create_index("backup_events_type_at", "backup_events", ["type", "at"])

    op.create_table(
        "backup_status",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        _tsz("heartbeat_at"),
        sa.Column("free_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_bytes", sa.BigInteger(), nullable=True),
        sa.Column("min_free_bytes", sa.BigInteger(), nullable=True),
        sa.Column("nightly_at", sa.Text(), nullable=False),
        sa.Column("external_dir", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("backup_dir_bytes", sa.BigInteger(), nullable=True),
        sa.Column("key_configured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("id = 1", name="backup_status_single_row"),
    )


def downgrade() -> None:
    op.drop_table("backup_status")
    op.drop_index("backup_events_type_at", table_name="backup_events")
    op.drop_table("backup_events")
    op.drop_index("backup_runs_created", table_name="backup_runs")
    op.drop_index("backup_runs_one_active", table_name="backup_runs")
    op.drop_table("backup_runs")
