"""Collaborator services from ``application/services/`` (REQUEST scope).

Kept separate from ``HandlersProvider``: these are composed *inside* a
handler, not use cases themselves, so they get their own provider per
``.claude/rules/backend/providers.md``'s "one provider module per
concern" — a handler's constructor list and this module's list answer
different questions ("what operation is this" vs. "what does it lean
on"), even though both resolve at the same scope today.
"""

from dishka import Provider, Scope, provide_all

from application.services import (
    ClaimsFactory,
    SalePriceParser,
    SlugNormalizer,
    TimezoneValidator,
    TokenIssuer,
)


class ApplicationServicesProvider(Provider):
    scope = Scope.REQUEST

    services = provide_all(
        ClaimsFactory,
        TokenIssuer,
        SalePriceParser,
        SlugNormalizer,
        TimezoneValidator,
    )
