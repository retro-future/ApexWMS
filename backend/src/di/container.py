"""Container factory — the composition root.

This is the only place that knows about every layer; each milestone adds
providers in ``di/providers/`` rather than scattering wiring through the
codebase.
"""

from dishka import AsyncContainer, make_async_container
from dishka.integrations.fastapi import FastapiProvider

from di.providers import (
    AuthorizationProvider,
    AuthProvider,
    ConfigProvider,
    HandlersProvider,
    MasterDbProvider,
    MasterRepositoriesProvider,
    SecurityProvider,
    TenantDbProvider,
    TenantRepositoriesProvider,
)
from infrastructure.config import Settings


def create_container(settings: Settings | None = None) -> AsyncContainer:
    return make_async_container(
        ConfigProvider(),
        MasterDbProvider(),
        TenantDbProvider(),
        SecurityProvider(),
        AuthorizationProvider(),
        AuthProvider(),
        MasterRepositoriesProvider(),
        TenantRepositoriesProvider(),
        HandlersProvider(),
        FastapiProvider(),
        context={Settings: settings or Settings()},
    )
