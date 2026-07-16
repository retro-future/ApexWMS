"""Settings provider."""

from dishka import Provider, Scope, from_context

from infrastructure.config import Settings


class ConfigProvider(Provider):
    settings = from_context(provides=Settings, scope=Scope.APP)
