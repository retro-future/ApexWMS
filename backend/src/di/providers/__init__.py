"""Dishka providers, one module per concern (PRD §7.5).

Scopes:
    APP     — settings, MasterDB engine, tenant engine registry; later the
              JWT service and PDF renderer.
    REQUEST — MasterDB/TenantDB sessions; later the authenticated user,
              UoW, repositories, and use cases.

Each milestone adds its providers as a new module here (M1: auth;
M7: pdf; ...) and registers them in ``di.container.create_container``.
"""

from di.providers.config import ConfigProvider
from di.providers.master_db import MasterDbProvider
from di.providers.tenant_db import TenantDbProvider

__all__ = ["ConfigProvider", "MasterDbProvider", "TenantDbProvider"]
