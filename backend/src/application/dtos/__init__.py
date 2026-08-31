"""Application-internal DTOs — frozen dataclasses that never cross an HTTP
boundary: DI-context values (``CurrentUser``, ``RequestedTenant``) and
carriers passed between collaborator services (``ClaimsFactory``,
``TokenIssuer``). CQRS messages are Pydantic models instead (see
``application/core/`` for the shared base classes): a ``Command``/``Query``
request shape is defined alongside its handler in
``application/commands/``/``application/queries/``, while its *response*
payload (a ``Result``/``PagedResult``'s ``TData``) lives in
``application/models/`` — see that package's docstring and
``.claude/rules/backend/cqrs-response-models.md``. The split from this
package is by role, not by layer: does this object cross a message boundary
that needs structural validation and JSON shape, or does it just carry
context through the DI graph?
"""

from application.dtos.ageing import AgeingRow
from application.dtos.auth_tokens import AuthTokens
from application.dtos.below_cost import BelowCostRow
from application.dtos.below_cost_alert import BelowCostAlert
from application.dtos.current_user import CurrentUser
from application.dtos.customer_debt import CreditInvoiceDebt, DebtorSummary
from application.dtos.discrepancy import Discrepancy
from application.dtos.financing_split import FinancingSplitRow
from application.dtos.inventory_value import InventoryValueRow, LocationInventoryValue
from application.dtos.issued_claims import IssuedClaims
from application.dtos.ledger_log import (
    FinancialLedgerRow,
    LedgerActor,
    MovementLogRow,
)
from application.dtos.letterhead import Letterhead
from application.dtos.line_input import LineInput
from application.dtos.month_end import AccrualFigures, DebtMovement, MonthEndReport
from application.dtos.needs_pricing import NeedsPricingReason, NeedsPricingRow
from application.dtos.owner_seed import OwnerSeed
from application.dtos.period import Period
from application.dtos.posting_entry import MoneyEffect, Posting, PostingEntry
from application.dtos.price_deviation import PriceDeviation
from application.dtos.refresh_token_parts import RefreshTokenParts
from application.dtos.rendered_document import RenderedDocument
from application.dtos.requested_tenant import RequestedTenant
from application.dtos.sales_summary import (
    LocationSales,
    SalesFigures,
    SalesSummary,
    SalesTotalsRow,
)
from application.dtos.stock_on_hand import (
    AccessoryOnHand,
    OnHandBucket,
    StockGroupBy,
    StockOnHandGroup,
)
from application.dtos.tenant_logo import TenantLogo
from application.dtos.unit_trace import (
    TraceEvent,
    TraceEventKind,
    UnitOrigin,
    UnitSale,
    UnitTrace,
)

__all__ = [
    "AccessoryOnHand",
    "AccrualFigures",
    "AgeingRow",
    "AuthTokens",
    "BelowCostAlert",
    "BelowCostRow",
    "CreditInvoiceDebt",
    "CurrentUser",
    "DebtMovement",
    "DebtorSummary",
    "Discrepancy",
    "FinancialLedgerRow",
    "FinancingSplitRow",
    "InventoryValueRow",
    "IssuedClaims",
    "LedgerActor",
    "Letterhead",
    "LineInput",
    "LocationInventoryValue",
    "LocationSales",
    "MoneyEffect",
    "MonthEndReport",
    "MovementLogRow",
    "NeedsPricingReason",
    "NeedsPricingRow",
    "OnHandBucket",
    "OwnerSeed",
    "Period",
    "Posting",
    "PostingEntry",
    "PriceDeviation",
    "RefreshTokenParts",
    "RenderedDocument",
    "RequestedTenant",
    "SalesFigures",
    "SalesSummary",
    "SalesTotalsRow",
    "StockGroupBy",
    "StockOnHandGroup",
    "TenantLogo",
    "TraceEvent",
    "TraceEventKind",
    "UnitOrigin",
    "UnitSale",
    "UnitTrace",
]
