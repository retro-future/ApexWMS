"""Whether this store balances a cash drawer.

Off for every existing store, because none of them was asked. The flag
decides one thing only: whether money that physically changed hands is
recorded as a ledger row, in both directions — taken at the counter on a
sale, handed out on a trade-in. No existing figure moves either way; a
till row belongs to no report but the raw ledger and the shift screens.

Revision ID: 0013_tenant_runs_till
Revises: 0012_tenant_payment_currency
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_tenant_runs_till"
down_revision = "0012_tenant_payment_currency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("runs_till", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "runs_till")
