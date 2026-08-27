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
    CostPoolReader,
    CountPoster,
    DeviceUnitLoader,
    DeviceUnitRepricer,
    DocumentLineBuilder,
    DocumentLoader,
    DocumentNumberer,
    InvoicePoster,
    LedgerPoster,
    PaymentPoster,
    ProductRepricer,
    ReceiptPoster,
    RemovalPoster,
    RemovalScanner,
    SalePriceParser,
    SlugNormalizer,
    StockOnHandReader,
    TimezoneValidator,
    TokenIssuer,
    UnitOriginGuard,
    UnitTraceAssembler,
)


class ApplicationServicesProvider(Provider):
    scope = Scope.REQUEST

    services = provide_all(
        ClaimsFactory,
        TokenIssuer,
        LedgerPoster,
        DeviceUnitLoader,
        DeviceUnitRepricer,
        ProductRepricer,
        SalePriceParser,
        # --- M4 purchasing & receiving ---
        DocumentNumberer,
        DocumentLineBuilder,
        DocumentLoader,
        ReceiptPoster,
        # --- M5 outbound ---
        CostPoolReader,
        StockOnHandReader,
        InvoicePoster,
        # --- M5b credit sales ---
        PaymentPoster,
        # --- M6 returns, counts & write-offs ---
        UnitOriginGuard,
        UnitTraceAssembler,
    UnitTraceAssembler,
        RemovalScanner,
        RemovalPoster,
        CountPoster,
        SlugNormalizer,
        TimezoneValidator,
    )
