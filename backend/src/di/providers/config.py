"""Settings provider, plus trivial derived-value providers.

``refresh_token_ttl``/``invite_ttl`` are one-line unit conversions from
``Settings`` — the kind of trivial logic providers may still do directly
(.claude/rules/backend/providers.md) — so that use cases needing a TTL can
be resolved via ``provide_all`` instead of a hand-written factory.
"""

from datetime import timedelta

from dishka import Provider, Scope, from_context, provide

from application.types import InviteTtl, RefreshTokenTtl
from infrastructure.config import Settings


class ConfigProvider(Provider):
    settings = from_context(provides=Settings, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def refresh_token_ttl(self, settings: Settings) -> RefreshTokenTtl:
        return RefreshTokenTtl(timedelta(days=settings.refresh_token_ttl_days))

    @provide(scope=Scope.APP)
    def invite_ttl(self, settings: Settings) -> InviteTtl:
        return InviteTtl(timedelta(hours=settings.invite_ttl_hours))
