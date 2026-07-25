"""Ports — the Protocols use cases depend on (PRD §7.3).

Infrastructure implements these; application never imports the
implementations. This is what lets every use case run against
in-memory fakes with no database.

Layout mirrors the two databases: ``repository.py``/``uow.py`` hold the
generic interfaces, ``master/`` the tenant registry and identity,
``tenant/`` what a store owns — including who works there.
"""

from application.ports.clock import Clock
from application.ports.master import (
    InvitationRepository,
    MasterUnitOfWork,
    RefreshTokenRepository,
    TenantRepository,
    UserAppRoleRepository,
    UserRepository,
    UserTenantAccessRepository,
)
from application.ports.provisioning import TenantProvisioner
from application.ports.repository import Repository
from application.ports.security import PasswordHasher, TokenService
from application.ports.tenancy import TenantScope, TenantWorkspace
from application.ports.tenant import (
    EmployeeRepository,
    TenantSettingsRepository,
    TenantUnitOfWork,
)
from application.ports.uow import UnitOfWork

__all__ = [
    "Clock",
    "EmployeeRepository",
    "InvitationRepository",
    "MasterUnitOfWork",
    "PasswordHasher",
    "RefreshTokenRepository",
    "Repository",
    "TenantProvisioner",
    "TenantRepository",
    "TenantScope",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
    "TenantWorkspace",
    "TokenService",
    "UnitOfWork",
    "UserAppRoleRepository",
    "UserRepository",
    "UserTenantAccessRepository",
]
