"""Ports — the Protocols use cases depend on (PRD §7.3).

Infrastructure implements these; application never imports the
implementations. This is what lets every use case run against
in-memory fakes with no database.

Layout mirrors the two databases: ``repository.py``/``uow.py`` hold the
generic interfaces, ``master/`` and ``tenant/`` the per-database ones.
"""

from application.ports.clock import Clock
from application.ports.master import (
    InvitationRepository,
    MasterUnitOfWork,
    MembershipRepository,
    RefreshTokenRepository,
    TenantRepository,
    UserRepository,
)
from application.ports.provisioning import TenantProvisioner
from application.ports.repository import Repository
from application.ports.security import PasswordHasher, TokenService
from application.ports.tenant import TenantSettingsRepository, TenantUnitOfWork
from application.ports.uow import UnitOfWork

__all__ = [
    "Clock",
    "InvitationRepository",
    "MasterUnitOfWork",
    "MembershipRepository",
    "PasswordHasher",
    "RefreshTokenRepository",
    "Repository",
    "TenantProvisioner",
    "TenantRepository",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
    "TokenService",
    "UnitOfWork",
    "UserRepository",
]
