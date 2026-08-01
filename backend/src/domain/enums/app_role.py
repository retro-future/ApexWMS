"""Platform-operator roles (PRD §2). MasterDB, on ``user_app_roles``.

Kept apart from ``TenantRole`` (``tenant_role.py``) on purpose — see that
module's docstring for why the two string spaces must never overlap.
"""

from enum import StrEnum

APP_PREFIX = "app."


class AppRole(StrEnum):
    """Platform-operator roles. MasterDB, on ``user_app_roles``."""

    SUPERADMIN = "app.superadmin"
    ADMIN = "app.admin"
