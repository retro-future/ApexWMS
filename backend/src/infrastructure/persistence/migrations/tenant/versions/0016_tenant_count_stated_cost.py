"""An operator's stated cost for a stock-count accessory surplus.

Only meaningful when the location has never held the accessory before, so
its cost pool has no average to book a surplus at (``CountPoster._line_value``).
The accessory twin of ``stock_count_units.acquisition_cost_minor`` (FR-6.4b).
Nullable for the same reason: every line counted before this migration was
either matched against an existing pool or left uncosted.

Revision ID: 0016_tenant_count_stated_cost
Revises: 0015_tenant_buyback_rate
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_tenant_count_stated_cost"
down_revision = "0015_tenant_buyback_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_count_lines",
        sa.Column("stated_unit_cost_minor", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_count_lines", "stated_unit_cost_minor")
