"""Legacy subscribers from the old Google Form (specs/014 data-model.md).

`legacy_imports` (one confirmed import), `legacy_subscribers` (insert-only, never deleted —
constitution Principle III), `legacy_images` (their card images in the private volume),
`legacy_import_previews` (temporary, unsaved readings of an uploaded file, deleted on confirm or
expiry), and `image_access_log.legacy_subscriber_id`.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def _ts(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def upgrade() -> None:
    op.create_table(
        "legacy_imports",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at"),
        sa.Column("file_name", sa.Text(), nullable=False),
        *(
            sa.Column(name, sa.Integer(), nullable=False)
            for name in (
                "rows_total",
                "imported",
                "skipped",
                "already_imported",
                "not_counted",
                "incomplete",
                "corrected",
            )
        ),
        sa.CheckConstraint("char_length(file_name) <= 200", name="legacy_imports_file_name"),
    )

    op.create_table(
        "legacy_subscribers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("import_id", sa.BigInteger(), sa.ForeignKey("legacy_imports.id"), nullable=False),
        sa.Column("legacy_number", sa.Text(), nullable=False),
        sa.Column("form_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("second_name", sa.Text(), nullable=True),
        sa.Column("third_name", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("family_number_file", sa.Text(), nullable=True),
        sa.Column("family_number", sa.Text(), nullable=True),
        sa.Column("family_key", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("phone_file", sa.Text(), nullable=True),
        sa.Column("status_text", sa.Text(), nullable=True),
        sa.Column("counts_in_check", sa.Boolean(), nullable=False),
        sa.Column("extra", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("incomplete", sa.Boolean(), nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("legacy_number", name="legacy_subscribers_legacy_number_key"),
        sa.CheckConstraint(
            "legacy_number ~ '^T3C-[0-9]{3}$'", name="legacy_subscribers_legacy_number"
        ),
        sa.CheckConstraint(
            "phone IS NULL OR phone ~ '^07[0-9]{9}$'", name="legacy_subscribers_phone"
        ),
    )
    op.create_index(
        "legacy_subscribers_phone",
        "legacy_subscribers",
        ["phone"],
        postgresql_where=sa.text("counts_in_check"),
    )
    op.create_index(
        "legacy_subscribers_family_key",
        "legacy_subscribers",
        ["family_key"],
        postgresql_where=sa.text("counts_in_check"),
    )

    op.create_table(
        "legacy_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "legacy_subscriber_id",
            sa.BigInteger(),
            sa.ForeignKey("legacy_subscribers.id"),
            nullable=False,
        ),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        _ts("created_at"),
        sa.CheckConstraint("side IN ('front', 'back')", name="legacy_images_side"),
        sa.UniqueConstraint(
            "legacy_subscriber_id", "side", name="legacy_images_subscriber_side_key"
        ),
    )

    op.create_table(
        "legacy_import_previews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        _ts("created_at"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("images_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("images_done", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows", JSONB(), nullable=False),
        sa.CheckConstraint(
            "status IN ('fetching', 'ready', 'failed')", name="legacy_import_previews_status"
        ),
    )
    op.create_index("legacy_import_previews_owner", "legacy_import_previews", ["created_by"])

    op.add_column(
        "image_access_log", sa.Column("legacy_subscriber_id", sa.BigInteger(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("image_access_log", "legacy_subscriber_id")
    op.drop_table("legacy_import_previews")
    op.drop_table("legacy_images")
    op.drop_table("legacy_subscribers")
    op.drop_table("legacy_imports")
