"""Two role systems, deliberately kept apart (PRD §2).

``AppRole`` is a platform role held by the people who *operate* ApexWMS;
it lives in MasterDB and has nothing to do with any one store.
``TenantRole`` is a job at one store; it lives in that store's own
database, on the ``employees`` row.

The ``app.`` / ``tenant.`` prefixes are the collision-avoidance
mechanism: the two string spaces cannot overlap, so a role or permission
check can never accidentally match across the systems. In the C#
reference the prefix is enforced in each constructor; here the values
carry it literally and the guard below fails at import time if one is
ever added without it.

The tenant permission matrix (§2.1) is not hierarchical — a Storekeeper
can receive goods but not sell, a Seller can sell but not receive — so
authorization compares permissions, never rank (see ``domain.permissions``).
"""

from enum import StrEnum

APP_PREFIX = "app."
TENANT_PREFIX = "tenant."


class AppRole(StrEnum):
    """Platform-operator roles. MasterDB, on ``user_app_roles``."""

    SUPERADMIN = "app.superadmin"
    ADMIN = "app.admin"


class TenantRole(StrEnum):
    """Roles within one store. TenantDB, on ``employees.role``."""

    OWNER = "tenant.owner"
    MANAGER = "tenant.manager"
    STOREKEEPER = "tenant.storekeeper"
    SELLER = "tenant.seller"


def _assert_namespaced() -> None:
    for role in AppRole:
        if not role.value.startswith(APP_PREFIX):
            raise ValueError(f"{role.name} must start with {APP_PREFIX!r}")
    for role in TenantRole:
        if not role.value.startswith(TENANT_PREFIX):
            raise ValueError(f"{role.name} must start with {TENANT_PREFIX!r}")


_assert_namespaced()
