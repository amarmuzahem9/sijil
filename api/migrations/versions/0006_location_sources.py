"""drafts: location sources «coords» and «search», Iraq bounding box (docs/system.md §5.2 v1.6)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-22
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("drafts_location_source", "drafts", type_="check")
    op.create_check_constraint(
        "drafts_location_source",
        "drafts",
        "location_source IS NULL OR location_source IN ('gps', 'map', 'coords', 'search')",
    )


def downgrade() -> None:
    # Older code only knows gps and map; a pin placed by typing or search counts as a map pin.
    op.execute(
        "UPDATE drafts SET location_source = 'map' WHERE location_source IN ('coords', 'search')"
    )
    op.drop_constraint("drafts_location_source", "drafts", type_="check")
    op.create_check_constraint(
        "drafts_location_source",
        "drafts",
        "location_source IS NULL OR location_source IN ('gps', 'map')",
    )
