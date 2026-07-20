"""Dishka providers, one module per concern (PRD §7.5).

Scopes:
    APP     — settings, MasterDB engine, tenant engine registry, security
              services, the tenant provisioner; later the PDF renderer.
    REQUEST — the authenticated user, MasterDB/TenantDB sessions, UoWs,
              repositories, and use cases.

Each milestone adds its providers as a new module here (M7: pdf; ...)
and registers them in ``di.container.create_container``.
"""

from di.providers.auth import AuthProvider
from di.providers.config import ConfigProvider
from di.providers.master_db import MasterDbProvider
from di.providers.repositories import RepositoriesProvider
from di.providers.security import SecurityProvider
from di.providers.tenant_db import TenantDbProvider
from di.providers.use_cases import UseCasesProvider

__all__ = [
    "AuthProvider",
    "ConfigProvider",
    "MasterDbProvider",
    "RepositoriesProvider",
    "SecurityProvider",
    "TenantDbProvider",
    "UseCasesProvider",
]
