"""SAS subscribers from the SAS export (specs/015 data-model.md).

`sas_imports` (one confirmed import), `sas_subscribers` (one per SAS username; updated only by a
confirmed re-import, never deleted — constitution Principle III), `sas_subscriber_changes`
(append-only before/after of every update, research R10), `sas_tower_mappings` (prefixes the admin
mapped to a tower or to «بلا برج»), `sas_import_previews` (temporary, deleted on confirm or expiry).
No column ever holds a `ct_password` value (research R3).

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

_PHONE = "~ '^07[0-9]{9}$'"


def _ts(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def _tower_fk() -> sa.Column:
    return sa.Column(
        "tower_id",
        sa.BigInteger(),
        sa.ForeignKey("towers.id", ondelete="RESTRICT"),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        "sas_imports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at"),
        sa.Column("file_name", sa.Text(), nullable=False),
        *(
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "rows_total",
                "added",
                "updated",
                "unchanged",
                "skipped",
                "missing_marked",
                "missing_cleared",
                "without_phone",
                "prefixes_mapped",
            )
        ),
        sa.CheckConstraint("char_length(file_name) <= 200", name="sas_imports_file_name"),
    )

    op.create_table(
        "sas_subscribers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("username_key", sa.Text(), nullable=False),
        sa.Column("sas_id", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("phone_file", sa.Text(), nullable=True),
        sa.Column("username_phone", sa.Text(), nullable=True),
        sa.Column("tower_prefix", sa.Text(), nullable=True),
        _tower_fk(),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sas_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_online_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("group_name", sa.Text(), nullable=True),
        sa.Column("parent_name", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "first_import_id", sa.BigInteger(), sa.ForeignKey("sas_imports.id"), nullable=False
        ),
        sa.Column(
            "last_import_id", sa.BigInteger(), sa.ForeignKey("sas_imports.id"), nullable=False
        ),
        sa.Column("missing_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "missing_import_id", sa.BigInteger(), sa.ForeignKey("sas_imports.id"), nullable=True
        ),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("username_key", name="sas_subscribers_username_key"),
        sa.CheckConstraint(f"phone IS NULL OR phone {_PHONE}", name="sas_subscribers_phone"),
        sa.CheckConstraint(
            f"username_phone IS NULL OR username_phone {_PHONE}",
            name="sas_subscribers_username_phone",
        ),
    )
    op.create_index("sas_subscribers_phone", "sas_subscribers", ["phone"])
    op.create_index("sas_subscribers_username_phone", "sas_subscribers", ["username_phone"])
    op.create_index("sas_subscribers_tower_id", "sas_subscribers", ["tower_id"])

    op.create_table(
        "sas_subscriber_changes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("import_id", sa.BigInteger(), sa.ForeignKey("sas_imports.id"), nullable=False),
        sa.Column(
            "sas_subscriber_id",
            sa.BigInteger(),
            sa.ForeignKey("sas_subscribers.id"),
            nullable=False,
        ),
        sa.Column("before", JSONB(), nullable=False),
        sa.Column("after", JSONB(), nullable=False),
        _ts("created_at"),
    )
    op.create_index(
        "sas_subscriber_changes_subscriber", "sas_subscriber_changes", ["sas_subscriber_id"]
    )

    op.create_table(
        "sas_tower_mappings",
        sa.Column("prefix", sa.Text(), primary_key=True),
        _tower_fk(),
        sa.Column("set_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        _ts("set_at"),
        sa.Column("import_id", sa.BigInteger(), sa.ForeignKey("sas_imports.id"), nullable=False),
    )

    op.create_table(
        "sas_import_previews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("rows", JSONB(), nullable=False),
        sa.Column("prefixes", JSONB(), nullable=False),
        sa.Column("missing_ids", JSONB(), nullable=False),
    )
    op.create_index("sas_import_previews_owner", "sas_import_previews", ["created_by"])


def downgrade() -> None:
    op.drop_table("sas_import_previews")
    op.drop_table("sas_tower_mappings")
    op.drop_table("sas_subscriber_changes")
    op.drop_table("sas_subscribers")
    op.drop_table("sas_imports")
