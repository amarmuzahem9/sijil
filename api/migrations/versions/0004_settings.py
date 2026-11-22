"""settings: areas, towers, plans, reward_tiers, app_settings (feature 004)

See specs/004-settings/data-model.md

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

MAX_AMOUNT = 10_000_000


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="areas_name_length"),
    )
    op.create_index("areas_name_key", "areas", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "towers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "area_id",
            sa.BigInteger(),
            sa.ForeignKey("areas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("code", name="towers_code_key"),
        sa.CheckConstraint("code ~ '^[A-Z0-9]{2,20}$'", name="towers_code_format"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="towers_name_length"),
    )
    op.create_index("towers_area_id_idx", "towers", ["area_id"])

    op.create_table(
        "plans",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("trial_price", sa.Integer(), nullable=False),
        sa.Column("second_price", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="plans_name_length"),
        sa.CheckConstraint(
            f"trial_price BETWEEN 0 AND {MAX_AMOUNT}", name="plans_trial_price_range"
        ),
        sa.CheckConstraint(
            f"second_price BETWEEN 0 AND {MAX_AMOUNT}", name="plans_second_price_range"
        ),
    )
    op.create_index("plans_name_key", "plans", [sa.text("lower(name)")], unique=True)

    tiers = op.create_table(
        "reward_tiers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("min_count", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Integer(), nullable=False),
        sa.UniqueConstraint("min_count", name="reward_tiers_min_count_key"),
        sa.CheckConstraint("min_count BETWEEN 0 AND 10000", name="reward_tiers_min_count_range"),
        sa.CheckConstraint(f"rate BETWEEN 1 AND {MAX_AMOUNT}", name="reward_tiers_rate_range"),
    )
    op.bulk_insert(
        tiers,
        [
            {"min_count": 0, "rate": 5000},
            {"min_count": 30, "rate": 7000},
            {"min_count": 50, "rate": 10000},
        ],
    )

    app_settings = op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.bulk_insert(app_settings, [{"key": "otp_validity_minutes", "value": 60}])


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("reward_tiers")
    op.drop_index("plans_name_key", table_name="plans")
    op.drop_table("plans")
    op.drop_index("towers_area_id_idx", table_name="towers")
    op.drop_table("towers")
    op.drop_index("areas_name_key", table_name="areas")
    op.drop_table("areas")
