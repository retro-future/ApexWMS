"""M2 catalog: products, suppliers, customers, and locations grown up.

``locations`` existed from 0001 as the provisioning seed's target, with no
entity behind it. It gains ``created_at`` (the list ordering every catalog
table shares) and a unique name.

Money is stored as a ``BIGINT`` of minor units alongside the product's own
currency — never a float, and never a 32-bit integer: a mid-range phone is
about 12 000 000 so'm and ``INTEGER`` overflows at roughly 175 of them
(PRD §11). There is one currency column per product, not one per amount,
because currency is a property of the product (§4.5 rule 3).

No table here carries a ``tenant_id``: isolation is physical (PRD §3.1).

Revision ID: 0002_tenant_catalog
Revises: 0001_tenant
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_tenant_catalog"
down_revision = "0001_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing tenants already hold a seeded "Main Store" row, so the column
    # arrives with a server default to backfill it, then loses the default —
    # every later row gets its timestamp from the application clock.
    op.add_column(
        "locations",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.alter_column("locations", "created_at", server_default=None)
    op.create_index("ix_locations_name", "locations", ["name"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("tracking_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("barcode", sa.String(20), nullable=True),
        sa.Column("default_sale_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    # Unique but nullable: Postgres treats NULLs as distinct, so every SERIAL
    # product can carry no barcode without colliding (FR-2.3).
    op.create_index("ix_products_barcode", "products", ["barcode"], unique=True)

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"], unique=True)

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Not unique: two people share a name. Phone is what a seller searches by.
    op.create_index("ix_customers_full_name", "customers", ["full_name"])
    op.create_index("ix_customers_phone", "customers", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_customers_phone", "customers")
    op.drop_index("ix_customers_full_name", "customers")
    op.drop_table("customers")

    op.drop_index("ix_suppliers_name", "suppliers")
    op.drop_table("suppliers")

    op.drop_index("ix_products_barcode", "products")
    op.drop_index("ix_products_sku", "products")
    op.drop_table("products")

    op.drop_index("ix_locations_name", "locations")
    op.drop_column("locations", "created_at")
