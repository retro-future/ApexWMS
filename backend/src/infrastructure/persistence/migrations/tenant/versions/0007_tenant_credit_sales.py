"""M5b credit sales: payment terms on a sale, and the payments that settle it.

Three decisions the column list does not explain on its own.

**The debt is a column and the balance is not.** ``sales_invoices.debt_minor``
is the som figure the seller wrote at the counter — a fact, entered once.
What the customer still owes is ``debt − Σ payments``, recomputed every
time it is read. There is no ``balance`` column anywhere, on the invoice or
on the customer, for the same reason there is no ``stock_levels`` row that
anything but a movement may write: a counter can drift away from the rows
behind it, and a figure recomputed from immutable history cannot.

**``payments`` has no currency column.** Every customer debt in the system
is som (§4.7) — the seller quotes the som total for a dollar-priced phone
and *that figure is the debt*, with no rate involved. ``financial_transactions``
carries a currency because a transaction need not belong to a product;
this table cannot be denominated any other way, so storing one would only
create something to disagree with ``Payment.__post_init__``.

**``reverses_payment_id`` is unique.** A mistaken payment is compensated by
a negative one (FR-11.8), never edited or deleted. The constraint is what
stops a payment being reversed twice, which would hand the customer their
money back on paper and then take the debt away again.

Revision ID: 0007_tenant_credit_sales
Revises: 0006_tenant_sales
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_tenant_credit_sales"
down_revision = "0006_tenant_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_companies_name", "credit_companies", ["name"], unique=True)

    # The server default backfills the invoices M5 already wrote, then goes
    # away: every sale from here on states how it was paid for.
    op.add_column(
        "sales_invoices",
        sa.Column(
            "payment_type", sa.String(20), nullable=False, server_default="paid_in_full"
        ),
    )
    op.alter_column("sales_invoices", "payment_type", server_default=None)
    op.add_column(
        "sales_invoices",
        sa.Column(
            "credit_company_id",
            sa.Uuid(),
            sa.ForeignKey("credit_companies.id"),
            nullable=True,
        ),
    )
    op.add_column("sales_invoices", sa.Column("contract_ref", sa.String(100), nullable=True))
    # Som, so exponent 0 — the minor amount is the som amount (FR-2.9).
    op.add_column("sales_invoices", sa.Column("debt_minor", sa.BigInteger(), nullable=True))
    op.create_index(
        "ix_sales_invoices_payment_type", "sales_invoices", ["payment_type"]
    )
    op.create_index(
        "ix_sales_invoices_credit_company", "sales_invoices", ["credit_company_id"]
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sales_invoice_id", sa.Uuid(), sa.ForeignKey("sales_invoices.id"), nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        # Signed: a negative row is the compensating entry for an earlier one.
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "reverses_payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=True
        ),
    )
    op.create_index("ix_payments_invoice", "payments", ["sales_invoice_id"])
    op.create_index("ix_payments_occurred_at", "payments", ["occurred_at"])
    op.create_index(
        "ix_payments_reverses", "payments", ["reverses_payment_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_payments_reverses", "payments")
    op.drop_index("ix_payments_occurred_at", "payments")
    op.drop_index("ix_payments_invoice", "payments")
    op.drop_table("payments")

    op.drop_index("ix_sales_invoices_credit_company", "sales_invoices")
    op.drop_index("ix_sales_invoices_payment_type", "sales_invoices")
    op.drop_column("sales_invoices", "debt_minor")
    op.drop_column("sales_invoices", "contract_ref")
    op.drop_column("sales_invoices", "credit_company_id")
    op.drop_column("sales_invoices", "payment_type")

    op.drop_index("ix_credit_companies_name", "credit_companies")
    op.drop_table("credit_companies")
