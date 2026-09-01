"""Resolves the request locale from the ``Accept-Language`` header.

A plain class rather than logic in a provider so it can be tested without
standing up the container (.claude/rules/backend/providers.md).
"""

from starlette.requests import Request

from application.localization.locale import Locale


class CurrentLocaleAccessor:
    def __init__(self, request: Request) -> None:
        self._request = request

    def get_locale(self) -> Locale:
        return Locale.parse(self._request.headers.get("accept-language"))
