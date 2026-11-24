"""«تم الربط» and its undo (specs/013 data-model.md).

`requests.linked_at` / `linked_by` hold the current link (cleared by an undo); `request_links`
keeps every link and undo, never edited (constitution Principle III). An undo notification now
needs its reason code.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_UNLINK_REASONS = "('not_linked_in_sas','by_mistake','other_request_linked','other')"
_OLD_NOTIFY = (
    "(kind NOT IN ('approved','linked') OR reason IS NULL) "
    "AND (kind NOT IN ('rejected','deleted') OR reason IS NOT NULL)"
)
_NEW_NOTIFY = (
    "(kind NOT IN ('approved','linked') OR reason IS NULL) "
    "AND (kind NOT IN ('rejected','deleted','unlinked') OR reason IS NOT NULL)"
)


def upgrade() -> None:
    op.add_column("requests", sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "requests",
        sa.Column("linked_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_check_constraint(
        "requests_linked_has_time",
        "requests",
        "(status = 'linked') = (linked_at IS NOT NULL AND linked_by IS NOT NULL)",
    )
    op.create_check_constraint(
        "requests_linked_approved", "requests", "status <> 'linked' OR approved_at IS NOT NULL"
    )
    op.create_index(
        "requests_awaiting_link",
        "requests",
        ["approved_at", "id"],
        postgresql_where=sa.text("status = 'approved' AND deleted_at IS NULL"),
    )
    op.create_index(
        "requests_linked_at",
        "requests",
        ["marketer_id", "linked_at"],
        postgresql_where=sa.text("status = 'linked'"),
    )
    op.create_index(
        "requests_linked_recent",
        "requests",
        [sa.text("linked_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("status = 'linked'"),
    )

    op.create_table(
        "request_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "request_id",
            sa.BigInteger(),
            sa.ForeignKey("requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint("kind IN ('linked','unlinked')", name="request_links_kind"),
        sa.CheckConstraint(
            "CASE WHEN kind = 'linked' THEN reason IS NULL "
            f"ELSE reason IS NOT NULL AND reason IN {_UNLINK_REASONS} END",
            name="request_links_reason",
        ),
    )
    op.create_index("request_links_request", "request_links", ["request_id", "id"])

    op.drop_constraint("notifications_reason_kind", "notifications", type_="check")
    op.create_check_constraint("notifications_reason_kind", "notifications", _NEW_NOTIFY)


def downgrade() -> None:
    op.drop_constraint("notifications_reason_kind", "notifications", type_="check")
    op.create_check_constraint("notifications_reason_kind", "notifications", _OLD_NOTIFY)
    op.drop_table("request_links")
    op.drop_index("requests_linked_recent", table_name="requests")
    op.drop_index("requests_linked_at", table_name="requests")
    op.drop_index("requests_awaiting_link", table_name="requests")
    op.drop_constraint("requests_linked_approved", "requests", type_="check")
    op.drop_constraint("requests_linked_has_time", "requests", type_="check")
    op.drop_column("requests", "linked_by")
    op.drop_column("requests", "linked_at")
