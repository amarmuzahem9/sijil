"""Commission payments (specs/017 data-model.md).

`commission_payments` holds one «تم الدفع» per marketer and Baghdad month with its locked figures;
`commission_payment_requests` the requests it counted, keyed by request so a request is paid at
most once (docs/system.md v1.23 §9). Both are append-only: the app never updates or deletes them.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_MAX_AMOUNT = 10_000_000


def upgrade() -> None:
    op.create_table(
        "commission_payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("marketer_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("tier_min_count", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("marketer_id", "month", name="commission_payments_marketer_month"),
        sa.CheckConstraint(
            "extract(day from month) = 1", name="commission_payments_month_first_day"
        ),
        sa.CheckConstraint("count > 0", name="commission_payments_count"),
        sa.CheckConstraint(
            "tier_min_count >= 0 AND tier_min_count <= count", name="commission_payments_tier"
        ),
        sa.CheckConstraint(
            f"rate BETWEEN 1 AND {_MAX_AMOUNT}", name="commission_payments_rate_range"
        ),
        sa.CheckConstraint("amount = count::bigint * rate", name="commission_payments_amount"),
    )
    op.create_index("commission_payments_month", "commission_payments", ["month"])
    op.create_table(
        "commission_payment_requests",
        sa.Column("request_id", sa.BigInteger(), sa.ForeignKey("requests.id"), primary_key=True),
        sa.Column(
            "payment_id",
            sa.BigInteger(),
            sa.ForeignKey("commission_payments.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "commission_payment_requests_payment", "commission_payment_requests", ["payment_id"]
    )


def downgrade() -> None:
    op.drop_index("commission_payment_requests_payment", "commission_payment_requests")
    op.drop_table("commission_payment_requests")
    op.drop_index("commission_payments_month", "commission_payments")
    op.drop_table("commission_payments")
