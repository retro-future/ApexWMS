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
    AccessoryLineWriter,
    BalanceVerifier,
    BelowCostChecker,
    CatalogCodeGenerator,
    ClaimsFactory,
    CostPoolReader,
    CountPoster,
    CustomerReturnPoster,
    CustomerReturnScanner,
    DeviceUnitLoader,
    DeviceUnitRepricer,
    DocumentLineBuilder,
    DocumentNumberer,
    InventoryValuer,
    InvoicePoster,
    LedgerPoster,
    MonthEndReporter,
    PaymentPoster,
    PeriodResolver,
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
        CatalogCodeGenerator,
        # --- M4 purchasing & receiving ---
        DocumentNumberer,
        DocumentLineBuilder,
        ReceiptPoster,
        BelowCostChecker,
        # --- M5 outbound ---
        CostPoolReader,
        StockOnHandReader,
        AccessoryLineWriter,
        InvoicePoster,
        # --- M5b credit sales ---
        PaymentPoster,
        # --- M6 returns, counts & write-offs ---
        UnitOriginGuard,
        UnitTraceAssembler,
        RemovalScanner,
        RemovalPoster,
        CustomerReturnScanner,
        CustomerReturnPoster,
        CountPoster,
        SlugNormalizer,
        TimezoneValidator,
        # --- M9 month-end close ---
        PeriodResolver,
        InventoryValuer,
        BalanceVerifier,
        MonthEndReporter,
    )
