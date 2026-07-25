"""The permission catalog and the two role maps over it (PRD §2.1)."""

import pytest

from domain.permissions import (
    APP_ROLE_PERMISSIONS,
    TENANT_ROLE_PERMISSIONS,
    Permission,
    permissions_for,
)
from domain.roles import APP_PREFIX, TENANT_PREFIX, AppRole, TenantRole


class TestNamespacing:
    """The prefixes are the collision-avoidance mechanism — the two string
    spaces must not overlap, or a check could match across role systems."""

    def test_app_roles_are_namespaced(self):
        assert all(r.value.startswith(APP_PREFIX) for r in AppRole)

    def test_tenant_roles_are_namespaced(self):
        assert all(r.value.startswith(TENANT_PREFIX) for r in TenantRole)

    def test_the_two_role_spaces_are_disjoint(self):
        assert {r.value for r in AppRole} & {r.value for r in TenantRole} == set()


class TestCatalog:
    def test_reflection_finds_every_module_constant(self):
        catalog = Permission.all()
        assert Permission.Users.Manage in catalog
        assert Permission.FinancialLedger.View in catalog
        assert Permission.Tenant.Manage in catalog

    def test_every_permission_is_module_qualified(self):
        # "Permission.<Module>.<Action>" — three dot-separated parts.
        assert all(p.count(".") == 2 for p in Permission.all())

    def test_no_duplicate_strings_across_modules(self):
        flat = [
            value
            for module in Permission.modules().values()
            for name, value in vars(module).items()
            if not name.startswith("_") and isinstance(value, str)
        ]
        assert len(flat) == len(set(flat))


class TestRolesDrawFromOneCatalog:
    """Both maps assign *subsets of the same strings* — that is what stops
    tenant roles and app roles colliding."""

    @pytest.mark.parametrize("role", list(AppRole))
    def test_app_role_permissions_are_all_in_the_catalog(self, role):
        assert APP_ROLE_PERMISSIONS[role]() <= Permission.all()

    @pytest.mark.parametrize("role", list(TenantRole))
    def test_tenant_role_permissions_are_all_in_the_catalog(self, role):
        assert TENANT_ROLE_PERMISSIONS[role]() <= Permission.all()

    def test_superadmin_holds_everything(self):
        assert APP_ROLE_PERMISSIONS[AppRole.SUPERADMIN]() == Permission.all()

    def test_admin_holds_everything_except_managing_other_admins(self):
        admin = APP_ROLE_PERMISSIONS[AppRole.ADMIN]()
        assert Permission.AppRoles.Manage not in admin
        assert admin == Permission.all() - {Permission.AppRoles.Manage}


class TestTheMatrixIsNotHierarchical:
    """PRD §2.1: a Storekeeper receives but cannot sell, a Seller sells but
    cannot receive. Neither outranks the other — the reason authorization
    compares permissions rather than rank."""

    def test_storekeeper_receives_but_cannot_sell(self):
        storekeeper = TENANT_ROLE_PERMISSIONS[TenantRole.STOREKEEPER]()
        assert Permission.Receiving.Manage in storekeeper
        assert Permission.Sales.Manage not in storekeeper

    def test_seller_sells_but_cannot_receive(self):
        seller = TENANT_ROLE_PERMISSIONS[TenantRole.SELLER]()
        assert Permission.Sales.Manage in seller
        assert Permission.Receiving.Manage not in seller

    def test_neither_is_a_subset_of_the_other(self):
        storekeeper = TENANT_ROLE_PERMISSIONS[TenantRole.STOREKEEPER]()
        seller = TENANT_ROLE_PERMISSIONS[TenantRole.SELLER]()
        assert not storekeeper <= seller
        assert not seller <= storekeeper


class TestCostVisibility:
    """FR-1.7: cost/margin is hidden from Storekeeper and Seller."""

    @pytest.mark.parametrize("role", [TenantRole.STOREKEEPER, TenantRole.SELLER])
    def test_cost_is_hidden(self, role):
        assert Permission.Cost.View not in TENANT_ROLE_PERMISSIONS[role]()

    @pytest.mark.parametrize("role", [TenantRole.OWNER, TenantRole.MANAGER])
    def test_cost_is_visible(self, role):
        assert Permission.Cost.View in TENANT_ROLE_PERMISSIONS[role]()


class TestOwnerOnlyOperations:
    """§2.1 reserves three rows to the Owner alone."""

    @pytest.mark.parametrize(
        "permission",
        [
            Permission.Users.Manage,
            Permission.TenantSettings.Manage,
            Permission.CreditCompany.Manage,
        ],
    )
    def test_manager_does_not_hold_it(self, permission):
        assert permission not in TENANT_ROLE_PERMISSIONS[TenantRole.MANAGER]()
        assert permission in TENANT_ROLE_PERMISSIONS[TenantRole.OWNER]()

    def test_owner_holds_everything_a_manager_does(self):
        owner = TENANT_ROLE_PERMISSIONS[TenantRole.OWNER]()
        assert TENANT_ROLE_PERMISSIONS[TenantRole.MANAGER]() <= owner

    @pytest.mark.parametrize(
        "role", [TenantRole.MANAGER, TenantRole.STOREKEEPER, TenantRole.SELLER]
    )
    def test_only_the_owner_can_even_see_the_staff_list(self, role):
        """PRD §8 makes GET /users Owner-only, not just the writes."""
        assert Permission.Users.View not in TENANT_ROLE_PERMISSIONS[role]()
        assert Permission.Users.View in TENANT_ROLE_PERMISSIONS[TenantRole.OWNER]()


class TestResolvingHeldPermissions:
    def test_a_tenant_role_alone(self):
        held = permissions_for(tenant_role=TenantRole.SELLER)
        assert held == TENANT_ROLE_PERMISSIONS[TenantRole.SELLER]()

    def test_an_app_role_alone(self):
        held = permissions_for(app_roles=[AppRole.SUPERADMIN])
        assert held == Permission.all()

    def test_roles_are_additive(self):
        held = permissions_for(
            app_roles=[AppRole.ADMIN], tenant_role=TenantRole.SELLER
        )
        assert Permission.AppRoles.Manage not in held
        assert Permission.Sales.Manage in held

    def test_no_roles_grants_nothing(self):
        assert permissions_for() == frozenset()

    def test_an_unknown_role_grants_nothing_rather_than_raising(self):
        # Tokens outlive role definitions; an unrecognised one must not 500.
        assert permissions_for(app_roles=["app.nonexistent"]) == frozenset()
