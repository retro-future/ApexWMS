"""MasterDB repositories — the tenant registry and platform identity (PRD §3.1).

Row ↔ entity mapping stays inside; nothing above this package sees a model.
"""

from .base import MasterCrudRepository
from .invitation import SqlInvitationRepository
from .refresh_token import SqlRefreshTokenRepository
from .tenant import SqlTenantRepository
from .user import SqlUserRepository
from .user_app_role import SqlUserAppRoleRepository
from .user_tenant_access import SqlUserTenantAccessRepository

__all__ = [
    "MasterCrudRepository",
    "SqlInvitationRepository",
    "SqlRefreshTokenRepository",
    "SqlTenantRepository",
    "SqlUserAppRoleRepository",
    "SqlUserRepository",
    "SqlUserTenantAccessRepository",
]
