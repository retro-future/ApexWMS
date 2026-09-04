"""Goods coming back from a customer, and the money going back with them.

Two columns here have no counterpart on ``supplier_return_lines``, and both
are the difference between the two documents.

``customer_return_lines.refund_price_minor`` exists because a customer is
paid back at a price somebody agreed to, while goods go back to a supplier
at their book value. It carries no currency column: like every other price,
it inherits the product's (§4.5 rule 3). What the goods *cost* is still
absent, for the reason 0008 gives.

``customer_returns.debt_relief_minor`` is som, so it needs no currency
column either — all customer debt is som (§4.7). It is deliberately not
derived from the refunds above it, which are in the products' own
currencies: converting between them would need a rate, and there is none
anywhere in this system.

Revision ID: 0011_tenant_customer_returns
Revises: 0010_tenant_catalog_codes
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_tenant_customer_returns"
down_revision = "0010_tenant_catalog_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_returns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        # Not nullable: goods with no sale behind them enter through a
        # stock count, which is the document that can say where they came
        # from.
        sa.Column(
            "sales_invoice_id",
            sa.Uuid(),
            sa.ForeignKey("sales_invoices.id"),
            nullable=False,
        ),
        # Nullable, mirroring the invoice: a sale may be to a walk-in.
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("debt_relief_minor", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_customer_returns_number", "customer_returns", ["number"], unique=True
    )
    op.create_index("ix_customer_returns_status", "customer_returns", ["status"])
    op.create_index("ix_customer_returns_invoice", "customer_returns", ["sales_invoice_id"])
    op.create_index("ix_customer_returns_customer", "customer_returns", ["customer_id"])
    op.create_index("ix_customer_returns_location", "customer_returns", ["location_id"])
    op.create_index("ix_customer_returns_reason", "customer_returns", ["reason"])

    op.create_table(
        "customer_return_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "customer_return_id",
            sa.Uuid(),
            sa.ForeignKey("customer_returns.id"),
            nullable=False,
        ),
        # The invoice line this unwinds: the refund's ceiling, and how the
        # confirm finds what the goods originally cost.
        sa.Column(
            "sales_invoice_line_id",
            sa.Uuid(),
            sa.ForeignKey("sales_invoice_lines.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("refund_price_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "refund_approved_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True
        ),
        sa.Column("refund_note", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_customer_return_lines_return", "customer_return_lines", ["customer_return_id"]
    )
    op.create_index(
        "ix_customer_return_lines_invoice_line",
        "customer_return_lines",
        ["sales_invoice_line_id"],
    )
    op.create_index(
        "ix_customer_return_lines_unit", "customer_return_lines", ["device_unit_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_customer_return_lines_unit", "customer_return_lines")
    op.drop_index("ix_customer_return_lines_invoice_line", "customer_return_lines")
    op.drop_index("ix_customer_return_lines_return", "customer_return_lines")
    op.drop_table("customer_return_lines")

    op.drop_index("ix_customer_returns_reason", "customer_returns")
    op.drop_index("ix_customer_returns_location", "customer_returns")
    op.drop_index("ix_customer_returns_customer", "customer_returns")
    op.drop_index("ix_customer_returns_invoice", "customer_returns")
    op.drop_index("ix_customer_returns_status", "customer_returns")
    op.drop_index("ix_customer_returns_number", "customer_returns")
    op.drop_table("customer_returns")
