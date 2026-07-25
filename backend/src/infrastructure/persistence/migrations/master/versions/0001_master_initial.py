"""Master schema: the tenant registry and platform identity (PRD §3.1, M1).

MasterDB answers "which tenants exist" and "who is this person". It holds
no operational data — that lives in each tenant's own database, alongside
the ``employees`` rows saying what a person may do *there*.

Revision ID: 0001_master
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_master"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        # The public handle an X-Tenant header names this tenant by (PRD §3.3).
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    op.create_table(
        "tenant_databases",
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), primary_key=True
        ),
        sa.Column("db_name", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # The login identity: one row per person, ever. `tenant_id` is their home
    # store, stamped into the access token at login; null for platform
    # operators, who belong to no store and get no tenant claim at all.
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # Identity's user_roles join, ported. A SuperAdmin is a user with
    # 'app.superadmin' here, not a separate kind of entity.
    op.create_table(
        "user_app_roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        # The surrogate primary key above keeps this entity the same shape as
        # every other one; this constraint is what stops a role being granted
        # twice, which a composite primary key would have done implicitly.
        sa.UniqueConstraint("user_id", "role", name="uq_user_app_roles_user_role"),
    )
    op.create_index("ix_user_app_roles_user_id", "user_app_roles", ["user_id"])

    # Extra stores a user may act in, beyond users.tenant_id. Checked before
    # an X-Tenant header is trusted (PRD §3.3).
    op.create_table(
        "user_tenant_access",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.UniqueConstraint(
            "user_id", "tenant_id", name="uq_user_tenant_access_user_tenant"
        ),
    )
    op.create_index("ix_user_tenant_access_user_id", "user_tenant_access", ["user_id"])

    # Central, so accepting an invitation does not require naming a tenant
    # first. tenant_id/tenant_role are set for an employee invite; app_role
    # for a platform-operator invite, which touches no tenant database.
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("tenant_role", sa.String(50), nullable=True),
        sa.Column("app_role", sa.String(50), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_invitations_email", "invitations", ["email"])

    # Master-side because login is: a refresh token proves who you are,
    # which is not a per-store fact.
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id", "refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_invitations_email", "invitations")
    op.drop_table("invitations")
    op.drop_index("ix_user_tenant_access_user_id", "user_tenant_access")
    op.drop_table("user_tenant_access")
    op.drop_index("ix_user_app_roles_user_id", "user_app_roles")
    op.drop_table("user_app_roles")
    op.drop_index("ix_users_tenant_id", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.drop_table("tenant_databases")
    op.drop_index("ix_tenants_slug", "tenants")
    op.drop_table("tenants")
