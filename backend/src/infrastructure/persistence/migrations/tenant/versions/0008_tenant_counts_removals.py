"""M6: the three internal and outbound documents §4.4 has been waiting on.

Two decisions the column list does not explain on its own.

**A stock count has four steps and three statuses.** ``stock_counts`` carries
its own ``closed_by``/``closed_at`` rather than a fourth ``DocumentStatus``
value, because only a count has a close and every other document would then
have a state it can never enter. Closing freezes the discrepancy report so
that what was reported and what gets applied describe the same shelf (FR-6.3).

**No line table here holds money.** A return, a write-off and a count
adjustment are all booked at the goods' *book value*, which is the unit's own
``acquisition_cost`` or the weighted-average pool replayed from the two
ledgers (§4.6). Storing that on the line would be a second opinion about a
figure the ledger already holds, free to drift from it. The one exception is
``stock_count_units.acquisition_cost_minor``, which is not a second opinion:
a handset the store has no row for has no cost anywhere else, and confirming
the count is what creates the unit that will carry it (FR-6.4b).

Revision ID: 0008_tenant_counts_removals
Revises: 0007_tenant_credit_sales
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_tenant_counts_removals"
down_revision = "0007_tenant_credit_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_returns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        # Not nullable, unlike a receipt's: nothing goes back to a walk-in.
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
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
        "ix_supplier_returns_number", "supplier_returns", ["number"], unique=True
    )
    op.create_index("ix_supplier_returns_status", "supplier_returns", ["status"])
    op.create_index("ix_supplier_returns_supplier", "supplier_returns", ["supplier_id"])
    op.create_index("ix_supplier_returns_location", "supplier_returns", ["location_id"])
    op.create_index("ix_supplier_returns_reason", "supplier_returns", ["reason"])

    op.create_table(
        "supplier_return_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "supplier_return_id",
            sa.Uuid(),
            sa.ForeignKey("supplier_returns.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_supplier_return_lines_return", "supplier_return_lines", ["supplier_return_id"]
    )
    op.create_index(
        "ix_supplier_return_lines_unit", "supplier_return_lines", ["device_unit_id"]
    )

    op.create_table(
        "write_offs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_write_offs_number", "write_offs", ["number"], unique=True)
    op.create_index("ix_write_offs_status", "write_offs", ["status"])
    op.create_index("ix_write_offs_location", "write_offs", ["location_id"])
    # "How much did we lose to theft this quarter" is what this indexes.
    op.create_index("ix_write_offs_reason", "write_offs", ["reason"])

    op.create_table(
        "write_off_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("write_off_id", sa.Uuid(), sa.ForeignKey("write_offs.id"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_write_off_lines_write_off", "write_off_lines", ["write_off_id"])
    op.create_index("ix_write_off_lines_unit", "write_off_lines", ["device_unit_id"])

    op.create_table(
        "stock_counts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_stock_counts_number", "stock_counts", ["number"], unique=True)
    op.create_index("ix_stock_counts_status", "stock_counts", ["status"])
    op.create_index("ix_stock_counts_location", "stock_counts", ["location_id"])

    op.create_table(
        "stock_count_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "stock_count_id", sa.Uuid(), sa.ForeignKey("stock_counts.id"), nullable=False
        ),
        sa.Column("imei", sa.String(15), nullable=False),
        # Null together, for a scan of an IMEI the store has no row for.
        sa.Column(
            "device_unit_id", sa.Uuid(), sa.ForeignKey("device_units.id"), nullable=True
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("expected", sa.Boolean(), nullable=False),
        sa.Column("scanned", sa.Boolean(), nullable=False),
        sa.Column("acquisition_cost_minor", sa.BigInteger(), nullable=True),
        # Per count, not global: the same IMEI is legitimately counted in
        # January and again in February.
        sa.UniqueConstraint("stock_count_id", "imei"),
    )
    op.create_index("ix_stock_count_units_count", "stock_count_units", ["stock_count_id"])
    op.create_index("ix_stock_count_units_imei", "stock_count_units", ["imei"])
    op.create_index("ix_stock_count_units_unit", "stock_count_units", ["device_unit_id"])

    op.create_table(
        "stock_count_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "stock_count_id", sa.Uuid(), sa.ForeignKey("stock_counts.id"), nullable=False
        ),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("expected_quantity", sa.Integer(), nullable=False),
        # Nullable: a shelf nobody looked at and a shelf found empty are
        # different findings.
        sa.Column("counted_quantity", sa.Integer(), nullable=True),
        sa.UniqueConstraint("stock_count_id", "product_id"),
    )
    op.create_index("ix_stock_count_lines_count", "stock_count_lines", ["stock_count_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_count_lines_count", "stock_count_lines")
    op.drop_table("stock_count_lines")

    op.drop_index("ix_stock_count_units_unit", "stock_count_units")
    op.drop_index("ix_stock_count_units_imei", "stock_count_units")
    op.drop_index("ix_stock_count_units_count", "stock_count_units")
    op.drop_table("stock_count_units")

    op.drop_index("ix_stock_counts_location", "stock_counts")
    op.drop_index("ix_stock_counts_status", "stock_counts")
    op.drop_index("ix_stock_counts_number", "stock_counts")
    op.drop_table("stock_counts")

    op.drop_index("ix_write_off_lines_unit", "write_off_lines")
    op.drop_index("ix_write_off_lines_write_off", "write_off_lines")
    op.drop_table("write_off_lines")

    op.drop_index("ix_write_offs_reason", "write_offs")
    op.drop_index("ix_write_offs_location", "write_offs")
    op.drop_index("ix_write_offs_status", "write_offs")
    op.drop_index("ix_write_offs_number", "write_offs")
    op.drop_table("write_offs")

    op.drop_index("ix_supplier_return_lines_unit", "supplier_return_lines")
    op.drop_index("ix_supplier_return_lines_return", "supplier_return_lines")
    op.drop_table("supplier_return_lines")

    op.drop_index("ix_supplier_returns_reason", "supplier_returns")
    op.drop_index("ix_supplier_returns_location", "supplier_returns")
    op.drop_index("ix_supplier_returns_supplier", "supplier_returns")
    op.drop_index("ix_supplier_returns_status", "supplier_returns")
    op.drop_index("ix_supplier_returns_number", "supplier_returns")
    op.drop_table("supplier_returns")
