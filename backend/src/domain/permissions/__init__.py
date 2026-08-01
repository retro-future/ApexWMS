"""One flat permission catalog, and the role -> permission resolution over
it (PRD §2.1), split by responsibility:

- ``catalog``   — the ``Permission`` enum itself.
- ``providers`` — ``RolePermissionProvider`` (the DIP seam) plus today's two
  static implementations, ``AppRolePermissionProvider`` and
  ``TenantRolePermissionProvider``.
- ``evaluator`` — ``PermissionEvaluator``, the domain service that resolves
  a caller's effective permissions from their app/tenant roles, plus
  ``permissions_for`` for domain-only callers that don't need DI.
"""

from domain.permissions.catalog import Permission
from domain.permissions.evaluator import PermissionEvaluator, permissions_for
from domain.permissions.providers import (
    AppRolePermissionProvider,
    RolePermissionProvider,
    TenantRolePermissionProvider,
)

__all__ = [
    "AppRolePermissionProvider",
    "Permission",
    "PermissionEvaluator",
    "RolePermissionProvider",
    "TenantRolePermissionProvider",
    "permissions_for",
]
