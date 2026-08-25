"""M7 documents: the third piece of the letterhead FR-8.1 names.

The image lives in the tenant's own database rather than a file store. A
store has one logo of a few dozen kilobytes, read only while a PDF renders,
and standing up object storage to hold it would add a deployment dependency
to a system that has none. If a tenant ever needs many files, that is the
point to reconsider — one column is far easier to move out than a file
store is to remove.

Revision ID: 0009_tenant_logo
Revises: 0008_tenant_counts_removals
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_tenant_logo"
down_revision = "0008_tenant_counts_removals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("logo", sa.LargeBinary(), nullable=True))
    op.add_column(
        "tenant_settings", sa.Column("logo_content_type", sa.String(40), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "logo_content_type")
    op.drop_column("tenant_settings", "logo")
