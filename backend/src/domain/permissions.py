"""One flat permission catalog, and the role → permission maps over it.

Ported from the C# reference's `Permissions.cs`: nested classes act as
*modules*, and the full catalog is derived by reflecting over them rather
than being maintained as a second list that can drift.

The point of a single catalog is that the two role systems
(``AppRole`` / ``TenantRole``) assign *subsets of the same strings*. A
tenant role can only ever reference this catalog, never an app-role name,
and vice versa — which is what keeps "custom permissions per tenant" from
colliding with platform roles.

Authorization compares permissions, not roles, because PRD §2.1's matrix
is not hierarchical: a Storekeeper receives goods but cannot sell, a
Seller sells but cannot receive. Neither outranks the other.
"""

from collections.abc import Callable, Iterable

from domain.roles import AppRole, TenantRole


class Permission:
    """Modules of the catalog. Values are the strings that get compared."""

    # --- platform level (held via AppRole, MasterDB) ----------------------
    class Tenant:
        View = "Permission.Tenant.View"
        Manage = "Permission.Tenant.Manage"

    class AppRoles:
        Manage = "Permission.AppRoles.Manage"

    # --- store level (held via TenantRole, TenantDB) ----------------------
    class Users:
        View = "Permission.Users.View"
        Manage = "Permission.Users.Manage"

    class TenantSettings:
        View = "Permission.TenantSettings.View"
        Manage = "Permission.TenantSettings.Manage"

    class Location:
        View = "Permission.Location.View"
        Manage = "Permission.Location.Manage"

    class Catalog:
        View = "Permission.Catalog.View"
        Manage = "Permission.Catalog.Manage"

    class Cost:
        """Acquisition cost and margin. Response-shaping, not just UI (FR-1.7)."""

        View = "Permission.Cost.View"

    class PurchaseOrder:
        View = "Permission.PurchaseOrder.View"
        Manage = "Permission.PurchaseOrder.Manage"

    class Receiving:
        View = "Permission.Receiving.View"
        Manage = "Permission.Receiving.Manage"

    class Sales:
        View = "Permission.Sales.View"
        Manage = "Permission.Sales.Manage"

    class Pricing:
        Override = "Permission.Pricing.Override"

    class CreditSale:
        Create = "Permission.CreditSale.Create"

    class CreditCompany:
        View = "Permission.CreditCompany.View"
        Manage = "Permission.CreditCompany.Manage"

    class Payment:
        Record = "Permission.Payment.Record"
        Reverse = "Permission.Payment.Reverse"

    class Customer:
        View = "Permission.Customer.View"
        Manage = "Permission.Customer.Manage"

    class CustomerAccount:
        View = "Permission.CustomerAccount.View"
        # The full debtor list across all customers is a business-health
        # figure, not a serving-this-customer one (PRD §2.1 note 1).
        ViewAll = "Permission.CustomerAccount.ViewAll"

    class SupplierReturn:
        View = "Permission.SupplierReturn.View"
        Manage = "Permission.SupplierReturn.Manage"

    class StockCount:
        Run = "Permission.StockCount.Run"
        Confirm = "Permission.StockCount.Confirm"

    class WriteOff:
        Manage = "Permission.WriteOff.Manage"

    class Document:
        View = "Permission.Document.View"
        Cancel = "Permission.Document.Cancel"

    class Scan:
        Lookup = "Permission.Scan.Lookup"

    class Reporting:
        View = "Permission.Reporting.View"

    class FinancialLedger:
        View = "Permission.FinancialLedger.View"

    @classmethod
    def modules(cls) -> dict[str, type]:
        return {
            name: member
            for name, member in vars(cls).items()
            if isinstance(member, type)
        }

    @classmethod
    def all(cls) -> frozenset[str]:
        return frozenset(
            value
            for module in cls.modules().values()
            for name, value in vars(module).items()
            if not name.startswith("_") and isinstance(value, str)
        )


def _of(*modules_or_permissions: type | str) -> frozenset[str]:
    """Every permission in the named modules, plus any named individually."""
    collected: set[str] = set()
    for item in modules_or_permissions:
        if isinstance(item, str):
            collected.add(item)
            continue
        collected.update(
            value
            for name, value in vars(item).items()
            if not name.startswith("_") and isinstance(value, str)
        )
    return frozenset(collected)


# --- platform roles ------------------------------------------------------

APP_ROLE_PERMISSIONS: dict[str, Callable[[], frozenset[str]]] = {
    AppRole.SUPERADMIN: Permission.all,
    # Everything except promoting or demoting other platform admins.
    AppRole.ADMIN: lambda: Permission.all() - {Permission.AppRoles.Manage},
}


# --- store roles (PRD §2.1, column by column) ----------------------------

_READ_ONLY_REFERENCE = _of(
    Permission.Catalog.View,
    Permission.Location.View,
    Permission.Scan.Lookup,
)

_SELLER = _READ_ONLY_REFERENCE | _of(
    Permission.Sales,
    Permission.CreditSale,
    Permission.Customer,
    Permission.CreditCompany.View,
    Permission.CustomerAccount.View,
    Permission.Payment.Record,
    Permission.Document.View,
    Permission.TenantSettings.View,
)

_STOREKEEPER = _READ_ONLY_REFERENCE | _of(
    Permission.Receiving,
    Permission.StockCount.Run,
    Permission.Document.View,
    Permission.TenantSettings.View,
)

_MANAGER = (
    _SELLER
    | _STOREKEEPER
    | _of(
        Permission.Catalog,
        Permission.Location,
        Permission.PurchaseOrder,
        Permission.SupplierReturn,
        Permission.Cost,
        Permission.Pricing,
        Permission.WriteOff,
        Permission.Reporting,
        Permission.FinancialLedger,
        Permission.StockCount.Confirm,
        Permission.Payment.Reverse,
        Permission.CustomerAccount.ViewAll,
        Permission.Document.Cancel,
    )
)

# Owner is Manager plus the three things §2.1 reserves to them alone.
_OWNER = _MANAGER | _of(
    Permission.Users,
    Permission.TenantSettings,
    Permission.CreditCompany,
)

TENANT_ROLE_PERMISSIONS: dict[str, Callable[[], frozenset[str]]] = {
    TenantRole.OWNER: lambda: _OWNER,
    TenantRole.MANAGER: lambda: _MANAGER,
    TenantRole.STOREKEEPER: lambda: _STOREKEEPER,
    TenantRole.SELLER: lambda: _SELLER,
}


def register_tenant_role(name: str, permissions: Callable[[], frozenset[str]]) -> None:
    """Hook for DB-driven per-tenant roles (see the reference's note on
    dynamic ``TenantRole``). Unused while §2.1 fixes the four roles."""
    TENANT_ROLE_PERMISSIONS[name] = permissions


def permissions_for(
    app_roles: Iterable[str] = (), tenant_role: str | None = None
) -> frozenset[str]:
    """Everything the holder of these roles may do.

    App and tenant roles are additive: a SuperAdmin who is also an Owner
    somewhere holds the union, and each half was drawn from the same catalog.
    """
    granted: set[str] = set()
    for role in app_roles:
        resolve = APP_ROLE_PERMISSIONS.get(role)
        if resolve is not None:
            granted |= resolve()
    if tenant_role is not None:
        resolve = TENANT_ROLE_PERMISSIONS.get(tenant_role)
        if resolve is not None:
            granted |= resolve()
    return frozenset(granted)
