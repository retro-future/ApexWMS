"""Dishka providers and container factory.

Scopes (PRD §7.5):
    APP     — settings, control-plane engine, engine registry, JWT, PDF.
    REQUEST — authenticated user, tenant session, UoW, repos, use cases.

M0 wires the APP scope with Settings only; each milestone adds providers
here rather than scattering wiring through the codebase.
"""

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from apexwms.infrastructure.config import Settings


class AppProvider(Provider):
    scope = Scope.APP

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    @provide
    def settings(self) -> Settings:
        return self._settings


def create_container(settings: Settings | None = None) -> AsyncContainer:
    return make_async_container(AppProvider(settings or Settings()))
