"""M4 inbound documents: purchase orders, goods receipts, and the scans on them.

Three decisions are worth stating, because none of them is obvious from
the column list.

**A scan is not a device unit.** ``goods_receipt_units`` looks a lot like
``device_units`` and is deliberately a separate table. A scan is a line on
a draft: it has no status, no location and no movement behind it, and the
handset it names does not exist in stock until the receipt is confirmed
(§4.3 rule 1). Its cost and asking price are nullable for the same reason
— a Storekeeper scans IMEIs and an Owner or Manager states the money
(FR-3.4b), and the draft is allowed to sit in between (FR-3.12).
Confirming is what creates the real unit and writes both ledgers.

**``goods_receipts.supplier_id`` is nullable.** Used stock arrives from
walk-in customers, and that receipt names no supplier at all;
``acquisition_source`` says which case it is (FR-3.3b). The alternative
was a supplier row called "Trade-in", which makes the supplier report lie.
Nothing here ties the source to the goods: ``condition`` is per scanned
handset, so a supplier delivery of used phones is an ordinary row.

**``document_sequences`` is a locked counter, not a Postgres sequence.** A
sequence is transaction-independent, so a rolled-back draft would burn its
number and a year's receipts would read 1, 2, 4, 7. A counter row locked
with ``SELECT ... FOR UPDATE`` rolls back with everything else, which is
what keeps the run dense enough that a gap means something.

Revision ID: 0005_tenant_documents
Revises: 0004_tenant_ledgers
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_tenant_documents"
down_revision = "0004_tenant_ledgers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        # Employee.id *is* the master User.id (§3.1), which is what lets
        # every actor on a document be a real foreign key.
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_purchase_orders_number", "purchase_orders", ["number"], unique=True)
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "purchase_order_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_orders.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        # Counts goods, not money: a plain INTEGER, and the column name
        # deliberately does not end in _minor.
        sa.Column("quantity", sa.Integer(), nullable=False),
        # Inherits the product's currency (§4.5 rule 3) — an order for a
        # USD phone and a UZS case holds two, and no column holds their sum.
        # Nullable while the order is a draft: a line may be raised before a
        # price is agreed, and ``PurchaseOrder.confirm`` refuses to confirm
        # while one is still missing.
        sa.Column("unit_cost_minor", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_purchase_order_lines_order", "purchase_order_lines", ["purchase_order_id"]
    )

    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("acquisition_source", sa.String(20), nullable=False),
        # Null for a trade-in: used stock is bought from a walk-in, and
        # that receipt names no supplier (FR-3.3b).
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column(
            "purchase_order_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_orders.id"),
            nullable=True,
        ),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_goods_receipts_number", "goods_receipts", ["number"], unique=True)
    op.create_index("ix_goods_receipts_status", "goods_receipts", ["status"])
    # "What did we take in from walk-ins this month?" — the question the
    # enum exists to make a query rather than a filter on a supplier's name.
    op.create_index("ix_goods_receipts_source", "goods_receipts", ["acquisition_source"])
    # FR-3.9: received against this order, for pending/partial/complete.
    op.create_index(
        "ix_goods_receipts_purchase_order", "goods_receipts", ["purchase_order_id"]
    )

    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "goods_receipt_id",
            sa.Uuid(),
            sa.ForeignKey("goods_receipts.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        # QUANTITY lines only, and nullable even there while the receipt is
        # a draft (FR-3.4b, FR-3.12). A serialized line prices each handset
        # individually, so it leaves this null.
        sa.Column("unit_cost_minor", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_goods_receipt_lines_receipt", "goods_receipt_lines", ["goods_receipt_id"]
    )

    op.create_table(
        "goods_receipt_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "goods_receipt_line_id",
            sa.Uuid(),
            sa.ForeignKey("goods_receipt_lines.id"),
            nullable=False,
        ),
        sa.Column("imei", sa.String(15), nullable=False),
        sa.Column("imei2", sa.String(15), nullable=True),
        sa.Column("serial_number", sa.String(64), nullable=True),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("acquisition_cost_minor", sa.BigInteger(), nullable=True),
        sa.Column("asking_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("cash_paid_minor", sa.BigInteger(), nullable=True),
        sa.Column("cash_paid_currency", sa.String(3), nullable=True),
        # Per line, not global. The same IMEI genuinely appears on two
        # receipts over a phone's life — received, returned, received again.
        # Store-wide uniqueness lives on device_units.imei, which is what
        # FR-3.5's scan-time check reads.
        sa.UniqueConstraint("goods_receipt_line_id", "imei"),
    )
    op.create_index(
        "ix_goods_receipt_units_line", "goods_receipt_units", ["goods_receipt_line_id"]
    )
    op.create_index("ix_goods_receipt_units_imei", "goods_receipt_units", ["imei"])

    op.create_table(
        "document_sequences",
        sa.Column("document_type", sa.String(30), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("document_sequences")

    op.drop_index("ix_goods_receipt_units_imei", "goods_receipt_units")
    op.drop_index("ix_goods_receipt_units_line", "goods_receipt_units")
    op.drop_table("goods_receipt_units")

    op.drop_index("ix_goods_receipt_lines_receipt", "goods_receipt_lines")
    op.drop_table("goods_receipt_lines")

    op.drop_index("ix_goods_receipts_purchase_order", "goods_receipts")
    op.drop_index("ix_goods_receipts_source", "goods_receipts")
    op.drop_index("ix_goods_receipts_status", "goods_receipts")
    op.drop_index("ix_goods_receipts_number", "goods_receipts")
    op.drop_table("goods_receipts")

    op.drop_index("ix_purchase_order_lines_order", "purchase_order_lines")
    op.drop_table("purchase_order_lines")

    op.drop_index("ix_purchase_orders_status", "purchase_orders")
    op.drop_index("ix_purchase_orders_number", "purchase_orders")
    op.drop_table("purchase_orders")
