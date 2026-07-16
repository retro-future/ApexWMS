"""Container factory — the composition root.

This is the only place that knows about every layer; each milestone adds
providers in ``providers.py`` rather than scattering wiring through the
codebase.
"""

from dishka import AsyncContainer, make_async_container
from dishka.integrations.fastapi import FastapiProvider

from di.providers import ConfigProvider, MasterDbProvider, TenantDbProvider
from infrastructure.config import Settings


def create_container(settings: Settings | None = None) -> AsyncContainer:
    return make_async_container(
        ConfigProvider(),
        MasterDbProvider(),
        TenantDbProvider(),
        FastapiProvider(),
        context={Settings: settings or Settings()},
    )
