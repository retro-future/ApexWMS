"""The counter behind a generated SKU (PH-000001) or in-store barcode.

One row per kind, no year: a catalog code is stable for the life of the
product, unlike a document number.

Revision ID: 0010_tenant_catalog_codes
Revises: 0009_tenant_logo
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_tenant_catalog_codes"
down_revision = "0009_tenant_logo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_code_sequences",
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("last_number", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("catalog_code_sequences")
