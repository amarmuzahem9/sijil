"""Notifications to the marketer (specs/012 data-model.md › New table `notifications`).

One row per event on one request: accepted, rejected, deleted (once each), linked and link undone
(013, may repeat). No personal data: the subscriber's name is read from `requests` at display
time, so a deletion (011) leaves nothing behind (system.md v1.17 §4.4).

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "marketer_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            sa.BigInteger(),
            sa.ForeignKey("requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('approved','rejected','linked','unlinked','deleted')",
            name="notifications_kind",
        ),
        sa.CheckConstraint(
            "(kind NOT IN ('approved','linked') OR reason IS NULL) "
            "AND (kind NOT IN ('rejected','deleted') OR reason IS NOT NULL)",
            name="notifications_reason_kind",
        ),
    )
    op.create_index(
        "notifications_once",
        "notifications",
        ["request_id", "kind"],
        unique=True,
        postgresql_where=sa.text("kind IN ('approved','rejected','deleted')"),
    )
    op.create_index(
        "notifications_marketer_id",
        "notifications",
        ["marketer_id", sa.text("id DESC")],
    )
    op.create_index(
        "notifications_unread",
        "notifications",
        ["marketer_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
