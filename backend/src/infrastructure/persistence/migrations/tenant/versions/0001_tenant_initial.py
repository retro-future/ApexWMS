"""Tenant schema, M1 minimum: locations and tenant_settings (PRD §3.4 seed).

Revision ID: 0001_tenant
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_tenant"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "tenant_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timezone", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tenant_settings")
    op.drop_table("locations")
