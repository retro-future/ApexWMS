"""A role within one store (PRD §2). TenantDB, on ``employees.role``.

Two role systems are deliberately kept apart: ``AppRole`` (``app_role.py``)
is held by the people who *operate* ApexWMS and lives in MasterDB;
``TenantRole`` is a job at one store and lives in that store's own
database. The ``app.``/``tenant.`` prefixes are the collision-avoidance
mechanism — the two string spaces cannot overlap, so a role or permission
check can never accidentally match across the systems (guarded by
``tests/architecture/test_role_namespacing.py``).

The tenant permission matrix (§2.1) is not hierarchical — a Storekeeper
can receive goods but not sell, a Seller can sell but not receive — so
authorization compares permissions, never rank (see ``domain.permissions``).
"""

from enum import StrEnum

TENANT_PREFIX = "tenant."


class TenantRole(StrEnum):
    """Roles within one store. TenantDB, on ``employees.role``."""

    OWNER = "tenant.owner"
    MANAGER = "tenant.manager"
    STOREKEEPER = "tenant.storekeeper"
    SELLER = "tenant.seller"
