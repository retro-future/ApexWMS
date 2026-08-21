"""Collaborator services composed inside command/query handlers.

Unlike a ``Command``/``Query``, nothing here is invoked directly from a
route or CLI command — these are plain constructor-injected helpers
shared by handlers: ``ClaimsFactory``/``TokenIssuer`` by ``LoginHandler``,
``RefreshTokensHandler``, and ``AcceptInviteHandler``; ``SalePriceParser``
and ``ProductRepricer`` by the product handlers;
``SlugNormalizer``/``TimezoneValidator`` by the tenant handlers.
"""

from application.services.claims import ClaimsFactory
from application.services.cost_pools import CostPoolReader
from application.services.device_unit_loader import DeviceUnitLoader
from application.services.device_unit_repricer import DeviceUnitRepricer
from application.services.document_lines import DocumentLineBuilder
from application.services.document_loader import DocumentLoader
from application.services.document_numbering import DocumentNumberer
from application.services.invoice_posting import InvoicePoster
from application.services.ledger import LedgerPoster
from application.services.product_repricer import ProductRepricer
from application.services.receipt_posting import ReceiptPoster
from application.services.sale_price import SalePriceParser
from application.services.slugs import SlugNormalizer
from application.services.timezones import TimezoneValidator
from application.services.token_issuer import TokenIssuer
from application.services.verification import (
    Discrepancy,
    LedgerReconciler,
    ProjectionVerifier,
)

__all__ = [
    "ClaimsFactory",
    "CostPoolReader",
    "DeviceUnitLoader",
    "DeviceUnitRepricer",
    "Discrepancy",
    "DocumentLineBuilder",
    "DocumentLoader",
    "DocumentNumberer",
    "InvoicePoster",
    "LedgerPoster",
    "LedgerReconciler",
    "ProductRepricer",
    "ProjectionVerifier",
    "ReceiptPoster",
    "SalePriceParser",
    "SlugNormalizer",
    "TimezoneValidator",
    "TokenIssuer",
]
