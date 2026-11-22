"""drafts: drafts, draft_images, image_access_log (feature 005)

See specs/005-subscriber-form/data-model.md

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_EDGE = 1600


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "marketer_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("subscriber_name", sa.Text(), nullable=True),
        sa.Column("national_id", sa.Text(), nullable=True),
        sa.Column("family_number", sa.Text(), nullable=True),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lng", sa.Float(), nullable=True),
        sa.Column("location_source", sa.Text(), nullable=True),
        sa.Column("location_accuracy_m", sa.Integer(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("landmark", sa.Text(), nullable=True),
        # Settings FKs use SET NULL: a draft is not a request, so it never "uses" an item
        # (research.md R2).
        sa.Column(
            "area_id",
            sa.BigInteger(),
            sa.ForeignKey("areas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tower_id",
            sa.BigInteger(),
            sa.ForeignKey("towers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "plan_id",
            sa.BigInteger(),
            sa.ForeignKey("plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("area_name", sa.Text(), nullable=True),
        sa.Column("tower_code", sa.Text(), nullable=True),
        sa.Column("plan_name", sa.Text(), nullable=True),
        sa.Column("trial_price", sa.Integer(), nullable=True),
        sa.Column("second_price", sa.Integer(), nullable=True),
        sa.Column("phone_input", sa.Text(), nullable=True),
        sa.Column("phone_normalized", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.CheckConstraint("status = 'draft'", name="drafts_status_draft"),
        sa.CheckConstraint(
            "subscriber_name IS NULL OR char_length(subscriber_name) <= 100",
            name="drafts_subscriber_name_length",
        ),
        sa.CheckConstraint(
            "national_id IS NULL OR char_length(national_id) <= 30",
            name="drafts_national_id_length",
        ),
        sa.CheckConstraint(
            "family_number IS NULL OR char_length(family_number) <= 30",
            name="drafts_family_number_length",
        ),
        sa.CheckConstraint(
            "address IS NULL OR char_length(address) <= 300", name="drafts_address_length"
        ),
        sa.CheckConstraint(
            "landmark IS NULL OR char_length(landmark) <= 200", name="drafts_landmark_length"
        ),
        sa.CheckConstraint(
            "phone_input IS NULL OR char_length(phone_input) <= 30",
            name="drafts_phone_input_length",
        ),
        sa.CheckConstraint(
            "(location_lat IS NULL) = (location_lng IS NULL)", name="drafts_location_pair"
        ),
        sa.CheckConstraint(
            "location_lat IS NULL OR location_lat BETWEEN -90 AND 90", name="drafts_location_lat"
        ),
        sa.CheckConstraint(
            "location_lng IS NULL OR location_lng BETWEEN -180 AND 180",
            name="drafts_location_lng",
        ),
        sa.CheckConstraint(
            "location_source IS NULL OR location_source IN ('gps', 'map')",
            name="drafts_location_source",
        ),
        sa.CheckConstraint(
            "location_accuracy_m IS NULL OR location_accuracy_m >= 0",
            name="drafts_location_accuracy",
        ),
        sa.CheckConstraint(
            "phone_normalized IS NULL OR phone_normalized ~ '^07[0-9]{9}$'",
            name="drafts_phone_normalized_format",
        ),
        sa.CheckConstraint("version >= 1", name="drafts_version_positive"),
    )
    op.create_index(
        "drafts_marketer_updated_idx", "drafts", ["marketer_id", sa.text("updated_at DESC")]
    )

    op.create_table(
        "draft_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.UniqueConstraint("draft_id", "side", name="draft_images_draft_side_key"),
        sa.CheckConstraint("side IN ('front', 'back')", name="draft_images_side"),
        sa.CheckConstraint(
            r"file_name ~ '^[0-9a-f]{32}\.jpg$'", name="draft_images_file_name_format"
        ),
        sa.CheckConstraint(
            f"size_bytes BETWEEN 1 AND {MAX_IMAGE_BYTES}", name="draft_images_size_range"
        ),
        sa.CheckConstraint(f"width BETWEEN 1 AND {MAX_IMAGE_EDGE}", name="draft_images_width"),
        sa.CheckConstraint(f"height BETWEEN 1 AND {MAX_IMAGE_EDGE}", name="draft_images_height"),
    )

    # Append-only; image_id/draft_id are plain values so the history outlives deletion (R8).
    op.create_table(
        "image_access_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("image_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.CheckConstraint("side IN ('front', 'back')", name="image_access_log_side"),
    )
    op.create_index(
        "image_access_log_created_at_idx", "image_access_log", [sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.drop_index("image_access_log_created_at_idx", table_name="image_access_log")
    op.drop_table("image_access_log")
    op.drop_table("draft_images")
    op.drop_index("drafts_marketer_updated_idx", table_name="drafts")
    op.drop_table("drafts")
