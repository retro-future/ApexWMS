"""What was physically handed over at the counter, in the currency it was in.

V1 recorded money only where a sale opened a debt, and every such debt is
som (§4.7), so ``payments`` needed no currency column. A sale settled at
confirm recorded nothing at all, which is why a till could not be balanced
against a dollar-priced handset paid for in cash som.

Existing rows are som by construction, so the backfill is a constant.

Revision ID: 0012_tenant_payment_currency
Revises: 0011_tenant_customer_returns
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_tenant_payment_currency"
down_revision = "0011_tenant_customer_returns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("currency", sa.String(3), nullable=True))
    op.execute("UPDATE payments SET currency = 'UZS'")
    op.alter_column("payments", "currency", nullable=False)


def downgrade() -> None:
    op.drop_column("payments", "currency")
