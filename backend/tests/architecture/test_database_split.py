"""The master/tenant split, enforced structurally (PRD §3.1).

The C# reference strips accidentally-included tenant types out of the
master model by reflection (``PruneTenantOnlyTypesForMaster``). SQLAlchemy
gives us the first half for free — ``MasterBase`` and ``TenantBase`` own
separate metadata, so a model physically cannot land in both — but nothing
stops someone declaring a tenant-shaped table on the wrong base. These
tests are that guard.

They are pure reflection over the mapped models: no database, no Docker.
"""

import domain.entities as entities
from domain.core import MasterEntity, TenantEntity
from infrastructure.persistence.master.models import MasterBase
from infrastructure.persistence.tenant.models import TenantBase

# The entity each model maps to. Kept explicit rather than inferred from
# names, so a rename cannot silently drop a table out of these checks.
MASTER_TABLES = {
    "tenants": entities.Tenant,
    "tenant_databases": None,  # registry plumbing, no domain entity
    "users": entities.User,
    "user_app_roles": entities.UserAppRole,
    "user_tenant_access": entities.UserTenantAccess,
    "invitations": entities.Invitation,
    "refresh_tokens": entities.RefreshTokenRecord,
}

TENANT_TABLES = {
    "employees": entities.Employee,
    "tenant_settings": None,  # singleton settings row
    # --- M2 catalog ---
    "products": entities.Product,
    "locations": entities.Location,
    "suppliers": entities.Supplier,
    "customers": entities.Customer,
}


class TestTablesLandInTheRightDatabase:
    def test_master_metadata_holds_exactly_the_expected_tables(self):
        assert set(MasterBase.metadata.tables) == set(MASTER_TABLES)

    def test_tenant_metadata_holds_exactly_the_expected_tables(self):
        assert set(TenantBase.metadata.tables) == set(TENANT_TABLES)

    def test_the_two_schemas_share_no_table(self):
        # The check that would have caught identity being in both places at
        # once during the migration between models.
        overlap = set(MasterBase.metadata.tables) & set(TenantBase.metadata.tables)
        assert overlap == set()


class TestEntityMarkersAgreeWithTheSchema:
    def test_every_master_table_maps_to_a_master_entity(self):
        for table, entity in MASTER_TABLES.items():
            if entity is None:
                continue
            assert issubclass(entity, MasterEntity), f"{table} → {entity.__name__}"
            assert not issubclass(entity, TenantEntity), f"{table} → {entity.__name__}"

    def test_every_tenant_table_maps_to_a_tenant_entity(self):
        for table, entity in TENANT_TABLES.items():
            if entity is None:
                continue
            assert issubclass(entity, TenantEntity), f"{table} → {entity.__name__}"
            assert not issubclass(entity, MasterEntity), f"{table} → {entity.__name__}"


class TestPhysicalIsolation:
    def test_no_tenant_table_carries_a_tenant_id(self):
        """A tenant_id column would mean isolation was a filter, not physical."""
        for name, table in TenantBase.metadata.tables.items():
            assert "tenant_id" not in table.columns, (
                f"{name}.tenant_id — isolation is the database, not a WHERE clause"
            )

    def test_money_columns_are_bigint(self):
        """A 32-bit integer overflows at about 175 phones' worth of som
        (PRD §11). The ceiling belongs in the schema, not in a code review."""
        for name, table in TenantBase.metadata.tables.items():
            for column in table.columns:
                if not column.name.endswith("_minor"):
                    continue
                assert column.type.__class__.__name__ == "BigInteger", (
                    f"{name}.{column.name} must be BIGINT"
                )

    def test_no_tenant_table_stores_money_as_a_float(self):
        """Lost fractions in an inventory system are indistinguishable from
        theft (PRD §4.5)."""
        for name, table in TenantBase.metadata.tables.items():
            for column in table.columns:
                assert "float" not in column.type.__class__.__name__.lower(), (
                    f"{name}.{column.name} is floating point"
                )

    def test_employees_and_users_agree_on_key_type(self):
        """``Employee.id`` *is* ``User.id`` — the ledger's FKs depend on it.

        No foreign key can express this (different databases), so the type
        agreement is the most the schema can assert.
        """
        users = MasterBase.metadata.tables["users"].columns["id"]
        employees = TenantBase.metadata.tables["employees"].columns["id"]
        assert type(users.type) is type(employees.type)
        assert users.primary_key and employees.primary_key


class TestJoinTablesKeepTheirUniqueness:
    """A surrogate id replaced the composite primary key on these, so the
    pair-uniqueness the composite key gave for free is now explicit."""

    def test_user_app_roles_cannot_grant_the_same_role_twice(self):
        table = MasterBase.metadata.tables["user_app_roles"]
        assert _has_unique_over(table, {"user_id", "role"})

    def test_user_tenant_access_cannot_grant_the_same_store_twice(self):
        table = MasterBase.metadata.tables["user_tenant_access"]
        assert _has_unique_over(table, {"user_id", "tenant_id"})


def _has_unique_over(table, columns: set[str]) -> bool:
    return any(
        {c.name for c in constraint.columns} == columns
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )
