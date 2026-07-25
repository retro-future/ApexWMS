"""Tenant schema, M1 minimum: employees plus the §3.4 provisioning seed.

`employees.id` is the master `users.id` — deliberately not a fresh
identifier. That is what lets tenant-side rows (from M3,
`stock_movements.user_id` and `documents.created_by`) be real foreign keys
into a tenant-local table while the login identity stays in MasterDB.

No table here carries a `tenant_id`: isolation is physical (PRD §3.1).

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
    # email/full_name are copied from the master user on purpose: listing a
    # store's staff, and later joining the ledger to a name, must not need a
    # cross-database read. MasterDB stays the source of truth.
    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_employees_email", "employees", ["email"], unique=True)

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
    op.drop_index("ix_employees_email", "employees")
    op.drop_table("employees")
