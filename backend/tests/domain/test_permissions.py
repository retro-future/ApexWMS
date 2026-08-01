"""The permission catalog and the two role providers over it (PRD §2.1)."""

import pytest

from domain.permissions import (
    AppRolePermissionProvider,
    Permission,
    PermissionEvaluator,
    RolePermissionProvider,
    TenantRolePermissionProvider,
    permissions_for,
)
from domain.roles import APP_PREFIX, TENANT_PREFIX, AppRole, TenantRole

_app_provider = AppRolePermissionProvider()
_tenant_provider = TenantRolePermissionProvider()


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
    def test_all_finds_every_member(self):
        catalog = Permission.all()
        assert Permission.USERS_MANAGE in catalog
        assert Permission.FINANCIAL_LEDGER_VIEW in catalog
        assert Permission.TENANT_MANAGE in catalog

    def test_every_permission_is_module_qualified(self):
        # "Permission.<Module>.<Action>" — three dot-separated parts.
        assert all(p.count(".") == 2 for p in Permission.all())

    def test_no_duplicate_values(self):
        # Belt-and-suspenders: @unique on Permission already makes a
        # duplicate value a class-definition-time error.
        values = [p.value for p in Permission]
        assert len(values) == len(set(values))


class TestRolesDrawFromOneCatalog:
    """Both providers assign *subsets of the same catalog* — that is what
    stops tenant roles and app roles colliding."""

    @pytest.mark.parametrize("role", list(AppRole))
    def test_app_role_permissions_are_all_in_the_catalog(self, role):
        assert _app_provider.get_permissions_for_role(role) <= Permission.all()

    @pytest.mark.parametrize("role", list(TenantRole))
    def test_tenant_role_permissions_are_all_in_the_catalog(self, role):
        assert _tenant_provider.get_permissions_for_role(role) <= Permission.all()

    def test_superadmin_holds_everything(self):
        assert _app_provider.get_permissions_for_role(AppRole.SUPERADMIN) == Permission.all()

    def test_admin_holds_everything_except_managing_other_admins(self):
        admin = _app_provider.get_permissions_for_role(AppRole.ADMIN)
        assert Permission.APP_ROLES_MANAGE not in admin
        assert admin == Permission.all() - {Permission.APP_ROLES_MANAGE}


class TestTheMatrixIsNotHierarchical:
    """PRD §2.1: a Storekeeper receives but cannot sell, a Seller sells but
    cannot receive. Neither outranks the other — the reason authorization
    compares permissions rather than rank."""

    def test_storekeeper_receives_but_cannot_sell(self):
        storekeeper = _tenant_provider.get_permissions_for_role(TenantRole.STOREKEEPER)
        assert Permission.RECEIVING_MANAGE in storekeeper
        assert Permission.SALES_MANAGE not in storekeeper

    def test_seller_sells_but_cannot_receive(self):
        seller = _tenant_provider.get_permissions_for_role(TenantRole.SELLER)
        assert Permission.SALES_MANAGE in seller
        assert Permission.RECEIVING_MANAGE not in seller

    def test_neither_is_a_subset_of_the_other(self):
        storekeeper = _tenant_provider.get_permissions_for_role(TenantRole.STOREKEEPER)
        seller = _tenant_provider.get_permissions_for_role(TenantRole.SELLER)
        assert not storekeeper <= seller
        assert not seller <= storekeeper


class TestCostVisibility:
    """FR-1.7: cost/margin is hidden from Storekeeper and Seller."""

    @pytest.mark.parametrize("role", [TenantRole.STOREKEEPER, TenantRole.SELLER])
    def test_cost_is_hidden(self, role):
        assert Permission.COST_VIEW not in _tenant_provider.get_permissions_for_role(role)

    @pytest.mark.parametrize("role", [TenantRole.OWNER, TenantRole.MANAGER])
    def test_cost_is_visible(self, role):
        assert Permission.COST_VIEW in _tenant_provider.get_permissions_for_role(role)


class TestOwnerOnlyOperations:
    """§2.1 reserves three rows to the Owner alone."""

    @pytest.mark.parametrize(
        "permission",
        [
            Permission.USERS_MANAGE,
            Permission.TENANT_SETTINGS_MANAGE,
            Permission.CREDIT_COMPANY_MANAGE,
        ],
    )
    def test_manager_does_not_hold_it(self, permission):
        manager = _tenant_provider.get_permissions_for_role(TenantRole.MANAGER)
        owner = _tenant_provider.get_permissions_for_role(TenantRole.OWNER)
        assert permission not in manager
        assert permission in owner

    def test_owner_holds_everything_a_manager_does(self):
        owner = _tenant_provider.get_permissions_for_role(TenantRole.OWNER)
        manager = _tenant_provider.get_permissions_for_role(TenantRole.MANAGER)
        assert manager <= owner

    @pytest.mark.parametrize(
        "role", [TenantRole.MANAGER, TenantRole.STOREKEEPER, TenantRole.SELLER]
    )
    def test_only_the_owner_can_even_see_the_staff_list(self, role):
        """PRD §8 makes GET /users Owner-only, not just the writes."""
        assert Permission.USERS_VIEW not in _tenant_provider.get_permissions_for_role(role)
        assert Permission.USERS_VIEW in _tenant_provider.get_permissions_for_role(TenantRole.OWNER)


class TestResolvingHeldPermissions:
    def test_a_tenant_role_alone(self):
        held = permissions_for(tenant_role=TenantRole.SELLER)
        assert held == _tenant_provider.get_permissions_for_role(TenantRole.SELLER)

    def test_an_app_role_alone(self):
        held = permissions_for(app_roles=[AppRole.SUPERADMIN])
        assert held == Permission.all()

    def test_roles_are_additive(self):
        held = permissions_for(app_roles=[AppRole.ADMIN], tenant_role=TenantRole.SELLER)
        assert Permission.APP_ROLES_MANAGE not in held
        assert Permission.SALES_MANAGE in held

    def test_no_roles_grants_nothing(self):
        assert permissions_for() == frozenset()

    def test_an_unknown_role_grants_nothing_rather_than_raising(self):
        # Tokens outlive role definitions; an unrecognised one must not 500.
        assert permissions_for(app_roles=["app.nonexistent"]) == frozenset()


class TestPermissionEvaluator:
    """The evaluator only depends on the ``RolePermissionProvider`` Protocol
    — this proves the DIP seam works with an arbitrary implementation, not
    just the two static providers shipped today."""

    class _StubProvider:
        def __init__(self, mapping: dict[str, frozenset[Permission]]) -> None:
            self._mapping = mapping

        def get_permissions_for_role(self, role: str) -> frozenset[Permission]:
            return self._mapping.get(role, frozenset())

    def test_evaluate_composes_arbitrary_providers(self):
        app_provider: RolePermissionProvider = self._StubProvider(
            {"stub.app": frozenset({Permission.SCAN_LOOKUP})}
        )
        tenant_provider: RolePermissionProvider = self._StubProvider(
            {"stub.tenant": frozenset({Permission.SALES_VIEW})}
        )
        evaluator = PermissionEvaluator(app_provider, tenant_provider)

        held = evaluator.evaluate(app_roles=["stub.app"], tenant_role="stub.tenant")

        assert held == frozenset({Permission.SCAN_LOOKUP, Permission.SALES_VIEW})
