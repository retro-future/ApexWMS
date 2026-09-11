"""The rate a used handset was bought at.

The trade-in twin of ``sales_invoices.sale_rate_id`` (W9 B2): a handset
valued in dollars and paid for in som records no rate, so nobody can say
afterwards what the store's own buying rate really was.

Nullable for the same reason as the sale side: every receipt confirmed
before this migration was struck at a rate nobody wrote down.

Revision ID: 0015_tenant_buyback_rate
Revises: 0014_tenant_exchange_rates
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_tenant_buyback_rate"
down_revision = "0014_tenant_exchange_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "goods_receipts",
        sa.Column("buyback_rate_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_goods_receipts_buyback_rate_id",
        "goods_receipts",
        "exchange_rates",
        ["buyback_rate_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_goods_receipts_buyback_rate_id", "goods_receipts", type_="foreignkey"
    )
    op.drop_column("goods_receipts", "buyback_rate_id")
