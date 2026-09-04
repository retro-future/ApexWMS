"""Role -> permission providers (PRD §2.1): the DIP seam a
``PermissionEvaluator`` depends on. ``RolePermissionProvider`` is the
abstraction; ``AppRolePermissionProvider`` and ``TenantRolePermissionProvider``
are today's only implementations — both static, in-memory, and immutable.

A future DB-driven per-tenant role source (see the module docstring in
``evaluator.py``) becomes a third implementation of this same Protocol,
constructed in ``infrastructure/`` and swapped in via DI — no change to the
evaluator or to these two classes required.
"""

from typing import Protocol

from domain.enums import AppRole, TenantRole
from domain.permissions.catalog import Permission


class RolePermissionProvider(Protocol):
    """A source of role -> permission-set mappings."""

    def get_permissions_for_role(self, role: str) -> frozenset[Permission]: ...


class AppRolePermissionProvider:
    """Platform-operator roles (MasterDB, ``user_app_roles``)."""

    def __init__(self) -> None:
        all_permissions = Permission.all()
        self._mappings: dict[str, frozenset[Permission]] = {
            AppRole.SUPERADMIN: all_permissions,
            # Everything except promoting or demoting other platform admins.
            AppRole.ADMIN: all_permissions - {Permission.APP_ROLES_MANAGE},
        }

    def get_permissions_for_role(self, role: str) -> frozenset[Permission]:
        return self._mappings.get(role, frozenset())


class TenantRolePermissionProvider:
    """Static store roles, column by column (PRD §2.1)."""

    def __init__(self) -> None:
        read_only_reference: frozenset[Permission] = frozenset(
            {
                Permission.CATALOG_VIEW,
                Permission.LOCATION_VIEW,
                Permission.SCAN_LOOKUP,
            }
        )

        seller = read_only_reference | frozenset(
            {
                Permission.SALES_VIEW,
                Permission.SALES_MANAGE,
                Permission.CREDIT_SALE_CREATE,
                Permission.CUSTOMER_VIEW,
                Permission.CUSTOMER_MANAGE,
                Permission.CREDIT_COMPANY_VIEW,
                Permission.CUSTOMER_ACCOUNT_VIEW,
                Permission.PAYMENT_RECORD,
                Permission.DOCUMENT_VIEW,
                Permission.TENANT_SETTINGS_VIEW,
            }
        )

        storekeeper = read_only_reference | frozenset(
            {
                Permission.RECEIVING_VIEW,
                Permission.RECEIVING_MANAGE,
                Permission.STOCK_COUNT_RUN,
                Permission.DOCUMENT_VIEW,
                Permission.TENANT_SETTINGS_VIEW,
            }
        )

        manager = (
            seller
            | storekeeper
            | frozenset(
                {
                    Permission.CATALOG_MANAGE,
                    Permission.LOCATION_MANAGE,
                    Permission.PURCHASE_ORDER_VIEW,
                    Permission.PURCHASE_ORDER_MANAGE,
                    Permission.CUSTOMER_RETURN_VIEW,
                    Permission.CUSTOMER_RETURN_MANAGE,
                    Permission.SUPPLIER_RETURN_VIEW,
                    Permission.SUPPLIER_RETURN_MANAGE,
                    Permission.COST_VIEW,
                    Permission.PRICING_SET,
                    Permission.PRICING_OVERRIDE,
                    Permission.WRITE_OFF_MANAGE,
                    Permission.REPORTING_VIEW,
                    Permission.FINANCIAL_LEDGER_VIEW,
                    Permission.STOCK_COUNT_CONFIRM,
                    Permission.PAYMENT_REVERSE,
                    Permission.CUSTOMER_ACCOUNT_VIEW_ALL,
                    Permission.DOCUMENT_CANCEL,
                }
            )
        )

        # Owner is Manager plus the three things §2.1 reserves to them alone.
        owner = manager | frozenset(
            {
                Permission.USERS_VIEW,
                Permission.USERS_MANAGE,
                Permission.TENANT_SETTINGS_MANAGE,
                Permission.CREDIT_COMPANY_MANAGE,
            }
        )

        self._mappings: dict[str, frozenset[Permission]] = {
            TenantRole.OWNER: owner,
            TenantRole.MANAGER: manager,
            TenantRole.STOREKEEPER: storekeeper,
            TenantRole.SELLER: seller,
        }

    def get_permissions_for_role(self, role: str) -> frozenset[Permission]:
        return self._mappings.get(role, frozenset())
