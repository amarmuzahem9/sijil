"""requests, request_reasons, request_images, request_number_seq, drafts.additional_confirmed_key
(feature 008)

A submitted draft becomes a `requests` row with every value fixed at submission (Principle IV);
the draft row is then removed. Requests are never deleted. See
specs/008-submission-decision/data-model.md.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=None if nullable else sa.text("now()"),
    )


def upgrade() -> None:
    op.execute("CREATE SEQUENCE request_number_seq START 1001 INCREMENT 1")

    op.create_table(
        "requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "marketer_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        # Names (system.md §5.1): seven required, two optional.
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("father_name", sa.Text(), nullable=False),
        sa.Column("grandfather_name", sa.Text(), nullable=False),
        sa.Column("great_grandfather_name", sa.Text(), nullable=False),
        sa.Column("surname", sa.Text(), nullable=True),  # null only with no_surname
        sa.Column("mother_first_name", sa.Text(), nullable=False),
        sa.Column("mother_second_name", sa.Text(), nullable=False),
        sa.Column("mother_third_name", sa.Text(), nullable=True),
        sa.Column("mother_surname", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("no_surname", sa.Boolean(), nullable=False),
        sa.Column("national_id", sa.Text(), nullable=False),
        sa.Column("national_id_input", sa.Text(), nullable=False),
        sa.Column("family_number", sa.Text(), nullable=False),
        sa.Column("family_key", sa.Text(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("birth_place", sa.Text(), nullable=False),
        sa.Column("issuing_authority", sa.Text(), nullable=False),
        sa.Column("card_fields", JSONB(), nullable=False),
        sa.Column("national_id_check", JSONB(), nullable=True),
        sa.Column("card_readings", JSONB(), nullable=False),
        sa.Column("location_lat", sa.Float(), nullable=False),
        sa.Column("location_lng", sa.Float(), nullable=False),
        sa.Column("location_source", sa.Text(), nullable=False),
        sa.Column("location_accuracy_m", sa.Integer(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("landmark", sa.Text(), nullable=False),
        sa.Column(
            "area_id",
            sa.BigInteger(),
            sa.ForeignKey("areas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tower_id",
            sa.BigInteger(),
            sa.ForeignKey("towers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.BigInteger(),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("area_name", sa.Text(), nullable=False),
        sa.Column("tower_code", sa.Text(), nullable=False),
        sa.Column("plan_name", sa.Text(), nullable=False),
        sa.Column("trial_price", sa.Integer(), nullable=False),
        sa.Column("second_price", sa.Integer(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        _ts("approved_at", nullable=True),
        sa.Column("approved_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("number", name="requests_number_key"),
        sa.UniqueConstraint("draft_id", name="requests_draft_id_key"),
        sa.CheckConstraint("type IN ('new','additional','return')", name="requests_type"),
        sa.CheckConstraint(
            "status IN ('pending_review','approved','rejected','linked')", name="requests_status"
        ),
        sa.CheckConstraint("NOT no_surname OR surname IS NULL", name="requests_no_surname"),
        sa.CheckConstraint("no_surname OR surname IS NOT NULL", name="requests_surname_required"),
        sa.CheckConstraint("national_id ~ '^[0-9]{12}$'", name="requests_national_id_format"),
        sa.CheckConstraint("family_key ~ '^[A-Z0-9]+$'", name="requests_family_key_format"),
        sa.CheckConstraint("phone ~ '^07[0-9]{9}$'", name="requests_phone_format"),
        sa.CheckConstraint(
            "status <> 'approved' OR approved_at IS NOT NULL", name="requests_approved_has_time"
        ),
        sa.CheckConstraint(
            "status <> 'pending_review' OR approved_at IS NULL", name="requests_pending_no_time"
        ),
    )
    op.create_index("requests_phone_idx", "requests", ["phone"])
    op.create_index("requests_national_id_idx", "requests", ["national_id"])
    op.create_index("requests_family_key_idx", "requests", ["family_key"])
    op.create_index(
        "requests_marketer_submitted_idx",
        "requests",
        ["marketer_id", sa.text("submitted_at DESC")],
    )

    op.create_table(
        "request_reasons",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "request_id",
            sa.BigInteger(),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("matched_source", sa.Text(), nullable=True),
        sa.Column("matched_ref", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _ts("created_at"),
        sa.CheckConstraint(
            "reason IN ('family_exists','numbers_edited','return')", name="request_reasons_reason"
        ),
    )
    op.execute(
        "ALTER TABLE request_reasons ADD CONSTRAINT request_reasons_unique "
        "UNIQUE NULLS NOT DISTINCT (request_id, reason, matched_source, matched_ref)"
    )

    op.create_table(
        "request_images",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            sa.BigInteger(),
            sa.ForeignKey("requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "side", name="request_images_request_side_key"),
        sa.CheckConstraint("side IN ('front','back')", name="request_images_side"),
    )

    op.add_column("drafts", sa.Column("additional_confirmed_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("drafts", "additional_confirmed_key")
    op.drop_table("request_images")
    op.drop_table("request_reasons")
    op.drop_index("requests_marketer_submitted_idx", table_name="requests")
    op.drop_index("requests_family_key_idx", table_name="requests")
    op.drop_index("requests_national_id_idx", table_name="requests")
    op.drop_index("requests_phone_idx", table_name="requests")
    op.drop_table("requests")
    op.execute("DROP SEQUENCE request_number_seq")
