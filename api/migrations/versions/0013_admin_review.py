"""Admin review of pending requests (specs/010 data-model.md).

- requests: the decision (accept by/at already exists; reject by/at/reason/note), the commission
  answer, the confirmed warnings, and the marketer's values as submitted (never changed by a pin).
- request_reasons: a state (open / resolved / not_applicable) and who changed or added a row.
- request_number_pins: one append-only row per pin, holding the value before and after
  (constitution III v1.2.1).
- image_access_log: may name a request instead of a draft.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

REJECTION_REASONS = (
    "card_unclear",
    "numbers_mismatch",
    "under_15_days",
    "active_subscription",
    "other",
)


def upgrade() -> None:
    # --- requests ---
    op.add_column("requests", sa.Column("submitted_national_id", sa.Text(), nullable=True))
    op.add_column("requests", sa.Column("submitted_family_number", sa.Text(), nullable=True))
    op.execute(
        "UPDATE requests SET submitted_national_id = national_id_input, "
        "submitted_family_number = family_number"
    )
    op.alter_column("requests", "submitted_national_id", nullable=False)
    op.alter_column("requests", "submitted_family_number", nullable=False)
    op.add_column(
        "requests",
        sa.Column("counts_commission", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("requests", sa.Column("approval_warnings", JSONB(), nullable=True))
    op.add_column("requests", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "requests",
        sa.Column("rejected_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("requests", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("requests", sa.Column("rejection_note", sa.Text(), nullable=True))
    codes = ",".join(f"'{c}'" for c in REJECTION_REASONS)
    op.create_check_constraint(
        "requests_rejection_reason",
        "requests",
        f"rejection_reason IS NULL OR rejection_reason IN ({codes})",
    )
    op.create_check_constraint(
        "requests_rejected_has_decision",
        "requests",
        "(status = 'rejected') = (rejected_at IS NOT NULL AND rejected_by IS NOT NULL "
        "AND rejection_reason IS NOT NULL)",
    )
    op.create_check_constraint(
        "requests_rejection_note",
        "requests",
        "CASE WHEN rejection_reason = 'other' "
        "THEN rejection_note IS NOT NULL AND btrim(rejection_note) <> '' "
        "ELSE rejection_note IS NULL END",
    )
    op.create_check_constraint(
        "requests_rejected_no_approval", "requests", "status <> 'rejected' OR approved_at IS NULL"
    )
    op.create_index(
        "requests_pending_idx",
        "requests",
        ["submitted_at"],
        postgresql_where=sa.text("status = 'pending_review'"),
    )

    # --- request_reasons ---
    op.add_column(
        "request_reasons",
        sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'open'")),
    )
    op.add_column(
        "request_reasons", sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "request_reasons",
        sa.Column("state_changed_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "request_reasons",
        sa.Column("added_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_check_constraint(
        "request_reasons_state", "request_reasons", "state IN ('open','resolved','not_applicable')"
    )

    # --- request_number_pins ---
    op.create_table(
        "request_number_pins",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "request_id",
            sa.BigInteger(),
            sa.ForeignKey("requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("pinned_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "field IN ('national_id','family_number')", name="request_number_pins_field"
        ),
        sa.CheckConstraint(
            "source IN ('reading','mrz','marketer','typed')", name="request_number_pins_source"
        ),
        sa.CheckConstraint(
            "source <> 'mrz' OR field = 'national_id'", name="request_number_pins_mrz_nid"
        ),
    )
    op.create_index(
        "request_number_pins_request_idx", "request_number_pins", ["request_id", "pinned_at"]
    )

    # --- image_access_log ---
    op.alter_column("image_access_log", "draft_id", nullable=True)
    op.add_column("image_access_log", sa.Column("request_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    # Dropping these columns would destroy review decisions and pins (Principles III, IV), and a
    # later upgrade could not rebuild them. Refuse instead of losing them silently.
    decided = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT (SELECT count(*) FROM requests WHERE status = 'rejected' "
                "OR rejected_at IS NOT NULL) + (SELECT count(*) FROM request_number_pins)"
            )
        )
        .scalar_one()
    )
    if decided:
        raise RuntimeError("0013 downgrade refused: rejected requests or number pins exist")
    # A request image open keeps the draft id too (research R9); fill any row that lacks it.
    op.execute(
        "UPDATE image_access_log l SET draft_id = r.draft_id FROM requests r "
        "WHERE l.draft_id IS NULL AND l.request_id = r.id"
    )
    op.drop_column("image_access_log", "request_id")
    op.alter_column("image_access_log", "draft_id", nullable=False)

    op.drop_index("request_number_pins_request_idx", table_name="request_number_pins")
    op.drop_table("request_number_pins")

    op.drop_constraint("request_reasons_state", "request_reasons", type_="check")
    for column in ("added_by", "state_changed_by", "state_changed_at", "state"):
        op.drop_column("request_reasons", column)

    op.drop_index("requests_pending_idx", table_name="requests")
    for name in (
        "requests_rejected_no_approval",
        "requests_rejection_note",
        "requests_rejected_has_decision",
        "requests_rejection_reason",
    ):
        op.drop_constraint(name, "requests", type_="check")
    for column in (
        "rejection_note",
        "rejection_reason",
        "rejected_by",
        "rejected_at",
        "approval_warnings",
        "counts_commission",
        "submitted_family_number",
        "submitted_national_id",
    ):
        op.drop_column("requests", column)
