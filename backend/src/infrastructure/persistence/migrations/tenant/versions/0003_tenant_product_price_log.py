"""The catalog-price log (PRD §4.5b, FR-2.19).

``products.default_sale_price_minor`` stops being a value anyone assigns
and becomes the projection of this table's latest row. The asymmetry this
closes: cutting one used handset by $40 was always going to be an
immutable row naming its author, while changing a *model's* price — which
governs every future sale of every unit of it — would have been a silent
``UPDATE``.

No currency column, on purpose. The amounts are bare minor units in the
product's own currency (§4.5 rule 3), which is immutable once the product
has history, so a join to ``products`` recovers it and no row can drift
out of step with the catalog entry it belongs to.

``user_id`` is a genuine foreign key into ``employees``. That is only
possible because ``Employee.id`` *is* the master ``User.id`` (§3.1) — the
first place that contract earns its keep.

Existing products are **not** backfilled with a synthetic first row: a
price that was set before anyone was recording who set it has no author
and no timestamp, and inventing them would put a fabricated fact into an
append-only table whose whole value is that it contains none.

Revision ID: 0003_tenant_product_price_log
Revises: 0002_tenant_catalog
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_tenant_product_price_log"
down_revision = "0002_tenant_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_price_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        # Null for the first pricing: it has no predecessor.
        sa.Column("old_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("new_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False),
    )
    # The log is always read along one axis — one product's history, newest
    # last — and the projection asks for its final row on every reprice.
    op.create_index(
        "ix_product_price_changes_product_id",
        "product_price_changes",
        ["product_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_price_changes_product_id", "product_price_changes")
    op.drop_table("product_price_changes")
