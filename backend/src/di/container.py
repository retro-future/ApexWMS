"""Container factory — the composition root.

This is the only place that knows about every layer; each milestone adds
providers in ``di/providers/`` rather than scattering wiring through the
codebase.
"""

from dishka import AsyncContainer, make_async_container
from dishka.integrations.fastapi import FastapiProvider

from di.providers import (
    AuthProvider,
    ConfigProvider,
    MasterDbProvider,
    RepositoriesProvider,
    SecurityProvider,
    TenantDbProvider,
    UseCasesProvider,
)
from infrastructure.config import Settings


def create_container(settings: Settings | None = None) -> AsyncContainer:
    return make_async_container(
        ConfigProvider(),
        MasterDbProvider(),
        TenantDbProvider(),
        SecurityProvider(),
        AuthProvider(),
        RepositoriesProvider(),
        UseCasesProvider(),
        FastapiProvider(),
        context={Settings: settings or Settings()},
    )
