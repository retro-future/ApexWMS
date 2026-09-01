"""Locale resolution and the message catalog.

``MessageCatalog`` is stateless once loaded, so it is APP scope like the
other read-only collaborators. The ``Locale`` for a request comes from
``CurrentLocaleAccessor`` (.claude/rules/backend/providers.md — the
provider only constructs and delegates).
"""

from dishka import Provider, Scope, provide
from fastapi import Request

from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale
from infrastructure.localization.current_locale_accessor import CurrentLocaleAccessor


class LocalizationProvider(Provider):
    @provide(scope=Scope.APP)
    def catalog(self) -> MessageCatalog:
        return MessageCatalog()

    @provide(scope=Scope.REQUEST)
    def locale_accessor(self, request: Request) -> CurrentLocaleAccessor:
        return CurrentLocaleAccessor(request)

    @provide(scope=Scope.REQUEST)
    def locale(self, accessor: CurrentLocaleAccessor) -> Locale:
        return accessor.get_locale()
