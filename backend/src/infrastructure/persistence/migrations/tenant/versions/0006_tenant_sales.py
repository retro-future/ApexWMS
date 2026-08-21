"""M5 outbound: sales invoices, their lines, and the letterhead a PDF needs.

Two decisions are worth stating, because neither is obvious from the
column list.

**A draft line holds no price.** ``resolved_price_minor`` and
``charged_price_minor`` are nullable and stay null for the whole life of a
draft. Both are written once, at confirm, from a price resolution that
runs again at that moment (FR-4.5b1), so a markdown made while the draft
sat open reaches the customer. Freezing the scan-time price would charge a
price the store has already abandoned and write a deviation nobody made
into FR-9.7's report. ``override_price_minor`` is the third and separate
fact: what a Manager typed, which survives re-resolution.

**``price_approved_by`` is on the line, not derived from the document.**
The person who approves a discount and the person who confirms the invoice
need not be the same (FR-4.5f); the ledger's ``user_id`` names the
confirmer, so without this column the deviation report would misattribute
the decision to whoever happened to be at the till.

The two ``tenant_settings`` columns are the letterhead FR-8.1 puts on a
printed invoice. A logo is not here: it needs a file store, and the
invoice is not blocked on it.

Revision ID: 0006_tenant_sales
Revises: 0005_tenant_documents
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_tenant_sales"
down_revision = "0005_tenant_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False),
        # Nullable: a walk-in buying a case for cash is not a record the
        # store needs to keep (FR-4.1).
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_sales_invoices_number", "sales_invoices", ["number"], unique=True)
    op.create_index("ix_sales_invoices_status", "sales_invoices", ["status"])
    op.create_index("ix_sales_invoices_location", "sales_invoices", ["location_id"])
    op.create_index("ix_sales_invoices_customer", "sales_invoices", ["customer_id"])

    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sales_invoice_id", sa.Uuid(), sa.ForeignKey("sales_invoices.id"), nullable=False
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        # Set for a serialized line and null for a quantity one: an
        # accessory has no per-unit identity to point at (§4.1).
        sa.Column("device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True),
        # Counts goods, not money — the name deliberately does not end in _minor.
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("override_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("price_approved_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("price_note", sa.String(500), nullable=True),
        sa.Column("resolved_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("charged_price_minor", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_sales_invoice_lines_invoice", "sales_invoice_lines", ["sales_invoice_id"])
    op.create_index("ix_sales_invoice_lines_unit", "sales_invoice_lines", ["device_unit_id"])

    op.add_column("tenant_settings", sa.Column("business_name", sa.String(200), nullable=True))
    op.add_column("tenant_settings", sa.Column("address", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_settings", "address")
    op.drop_column("tenant_settings", "business_name")

    op.drop_index("ix_sales_invoice_lines_unit", "sales_invoice_lines")
    op.drop_index("ix_sales_invoice_lines_invoice", "sales_invoice_lines")
    op.drop_table("sales_invoice_lines")

    op.drop_index("ix_sales_invoices_customer", "sales_invoices")
    op.drop_index("ix_sales_invoices_location", "sales_invoices")
    op.drop_index("ix_sales_invoices_status", "sales_invoices")
    op.drop_index("ix_sales_invoices_number", "sales_invoices")
    op.drop_table("sales_invoices")
