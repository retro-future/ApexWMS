"""M3: the two append-only ledgers, and the handsets they move.

``stock_movements`` and ``financial_transactions`` are the backbone every
later milestone writes into — a confirm records goods *and* money in one
database transaction or neither (FR-10.1). ``stock_levels`` and
``device_units.status``/``location_id`` are projections of the first, kept
in step by the same posting and rebuildable from it by
``verify-projections``.

Three decisions worth stating here rather than rediscovering later:

- **Money columns are ``BIGINT`` and inherit the product's currency.**
  ``device_units`` and ``device_unit_price_changes`` carry no currency
  column at all (§4.5 rule 3); ``financial_transactions`` does, because a
  ``PAYMENT_RECEIVED`` entry is som against an invoice that may hold
  dollar lines and belongs to no single product (§4.7).
- **``cash_paid`` is the one place two currencies meet on one row**, and it
  is inert by construction: informational, in no ledger, in no total, in
  no report figure (FR-3.4d). Any query that sums it is a bug.
- **``user_id`` is a real foreign key into ``employees``.** No constraint
  can express that ``Employee.id`` *is* the master ``User.id`` across two
  databases (§3.1), but this is what that contract was for: the ledger's
  author is enforceable rather than a loose UUID.

``document_id`` deliberately carries no foreign key — the six document
types live in six different tables, and ``document_type`` says which.

Revision ID: 0004_tenant_ledgers
Revises: 0003_tenant_product_price_log
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_tenant_ledgers"
down_revision = "0003_tenant_product_price_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("imei", sa.String(15), nullable=False),
        sa.Column("imei2", sa.String(15), nullable=True),
        sa.Column("serial_number", sa.String(64), nullable=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        # Null once the unit has left the store.
        sa.Column(
            "location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column("acquisition_cost_minor", sa.BigInteger(), nullable=False),
        sa.Column("asking_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("cash_paid_minor", sa.BigInteger(), nullable=True),
        sa.Column("cash_paid_currency", sa.String(3), nullable=True),
        sa.Column("source_document_type", sa.String(30), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # FR-3.5: a duplicate IMEI is either a scanning error or a stolen-goods
    # red flag, and is rejected at scan time. The unique index is what makes
    # that check a guarantee rather than a race.
    op.create_index("ix_device_units_imei", "device_units", ["imei"], unique=True)
    # The needs-pricing worklist and the ageing report both sweep what is
    # currently on the shelf (FR-9.4, FR-9.6).
    op.create_index(
        "ix_device_units_status_location", "device_units", ["status", "location_id"]
    )

    op.create_table(
        "device_unit_price_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("old_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("new_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
    )
    op.create_index(
        "ix_device_unit_price_changes_unit",
        "device_unit_price_changes",
        ["device_unit_id", "occurred_at"],
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True
        ),
        sa.Column(
            "location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False
        ),
        # Counts goods, not money: a plain INTEGER is right, and the column
        # name deliberately does not end in _minor.
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
    )
    # "How did this IMEI end up here?" — one table, ordered by time (§4.3).
    op.create_index(
        "ix_stock_movements_unit", "stock_movements", ["device_unit_id", "occurred_at"]
    )
    # Rebuilding a level from the ledger, which verify-projections does for
    # every (product, location) pair in the store.
    op.create_index(
        "ix_stock_movements_product_location",
        "stock_movements",
        ["product_id", "location_id"],
    )
    # Cancellation: "find everything this document wrote" (FR-4.8).
    op.create_index(
        "ix_stock_movements_document", "stock_movements", ["document_type", "document_id"]
    )
    op.create_index("ix_stock_movements_occurred_at", "stock_movements", ["occurred_at"])

    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("txn_type", sa.String(30), nullable=False),
        # Signed: the direction of §4.6 is the sign, not a second column.
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=True
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
    )
    # The month-end report is a grouping query over a period (§5.10), and
    # the reconciliation replays the ledger since inception.
    op.create_index(
        "ix_financial_transactions_occurred_at", "financial_transactions", ["occurred_at"]
    )
    op.create_index(
        "ix_financial_transactions_type", "financial_transactions", ["txn_type"]
    )
    op.create_index(
        "ix_financial_transactions_document",
        "financial_transactions",
        ["document_type", "document_id"],
    )

    op.create_table(
        "stock_levels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        # Without this, two rows could describe the same product at the same
        # location and "the level" would have no single value for the ledger
        # to be reconciled against.
        sa.UniqueConstraint("product_id", "location_id"),
    )


def downgrade() -> None:
    op.drop_table("stock_levels")

    op.drop_index("ix_financial_transactions_document", "financial_transactions")
    op.drop_index("ix_financial_transactions_type", "financial_transactions")
    op.drop_index("ix_financial_transactions_occurred_at", "financial_transactions")
    op.drop_table("financial_transactions")

    op.drop_index("ix_stock_movements_occurred_at", "stock_movements")
    op.drop_index("ix_stock_movements_document", "stock_movements")
    op.drop_index("ix_stock_movements_product_location", "stock_movements")
    op.drop_index("ix_stock_movements_unit", "stock_movements")
    op.drop_table("stock_movements")

    op.drop_index("ix_device_unit_price_changes_unit", "device_unit_price_changes")
    op.drop_table("device_unit_price_changes")

    op.drop_index("ix_device_units_status_location", "device_units")
    op.drop_index("ix_device_units_imei", "device_units")
    op.drop_table("device_units")
