"""Dishka providers, one module per concern (PRD §7.5).

Scopes:
    APP     — settings, MasterDB engine, tenant engine registry, security
              services, the tenant provisioner, stateless domain
              collaborators (e.g. ``UnitProjector``) and the PDF renderer.
    REQUEST — the authenticated user, MasterDB/TenantDB sessions, UoWs,
              repositories, and command/query handlers.

Each milestone adds its providers as a new module here and registers
them in ``di.container.create_container``.
"""

from di.providers.auth import AuthProvider
from di.providers.authorization import AuthorizationProvider
from di.providers.config import ConfigProvider
from di.providers.documents import DocumentsProvider
from di.providers.domain_services import DomainServicesProvider
from di.providers.handlers import HandlersProvider
from di.providers.master_db import MasterDbProvider
from di.providers.master_repositories import MasterRepositoriesProvider
from di.providers.security import SecurityProvider
from di.providers.services import ApplicationServicesProvider
from di.providers.tenant_db import TenantDbProvider
from di.providers.tenant_repositories import TenantRepositoriesProvider

__all__ = [
    "ApplicationServicesProvider",
    "AuthProvider",
    "AuthorizationProvider",
    "ConfigProvider",
    "DocumentsProvider",
    "DomainServicesProvider",
    "HandlersProvider",
    "MasterDbProvider",
    "MasterRepositoriesProvider",
    "SecurityProvider",
    "TenantDbProvider",
    "TenantRepositoriesProvider",
]
