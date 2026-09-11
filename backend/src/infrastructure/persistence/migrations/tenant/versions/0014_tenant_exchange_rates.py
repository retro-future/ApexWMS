"""The rate a store quotes, and the rate a sale was struck at.

Two tables' worth of change for one fact V1 never wrote down: a dollar
price paid in som records no rate anywhere, so nobody can say afterwards
what the sale was actually struck at (W9 B1). ``exchange_rates`` is
append-only; ``sales_invoices.sale_rate_id`` points at the row in force
when the invoice was confirmed, which is what keeps a closed month from
moving when tomorrow's rate is entered.

Nullable on purpose: every invoice confirmed before this migration was
struck at a rate nobody recorded, and inventing one would be worse than
admitting it.

Revision ID: 0014_tenant_exchange_rates
Revises: 0013_tenant_runs_till
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_tenant_exchange_rates"
down_revision = "0013_tenant_runs_till"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("som_per_usd", sa.Numeric(18, 4), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_exchange_rates_kind_day",
        "exchange_rates",
        ["kind", "effective_on", "set_at"],
    )
    op.add_column(
        "sales_invoices",
        sa.Column("sale_rate_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sales_invoices_sale_rate_id",
        "sales_invoices",
        "exchange_rates",
        ["sale_rate_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_sales_invoices_sale_rate_id", "sales_invoices", type_="foreignkey"
    )
    op.drop_column("sales_invoices", "sale_rate_id")
    op.drop_index("ix_exchange_rates_kind_day", table_name="exchange_rates")
    op.drop_table("exchange_rates")
