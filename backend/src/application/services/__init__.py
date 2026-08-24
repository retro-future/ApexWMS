"""Collaborator services composed inside command/query handlers.

Unlike a ``Command``/``Query``, nothing here is invoked directly from a
route — these are plain constructor-injected helpers shared by handlers:
``ClaimsFactory``/``TokenIssuer`` by ``LoginHandler``,
``RefreshTokensHandler``, and ``AcceptInviteHandler``; ``SalePriceParser``
and ``ProductRepricer`` by the product handlers;
``SlugNormalizer``/``TimezoneValidator`` by the tenant handlers.

The posters are the weightiest of them. ``LedgerPoster`` writes both
ledgers and moves what they project, and the rest sit on top of it, one per
document a confirm turns into rows: ``ReceiptPoster``, ``InvoicePoster``,
``PaymentPoster``, ``CountPoster``, and ``RemovalPoster`` for the two
documents that take goods off the shelf for good. None of them commits —
the calling handler owns the transaction.

``verification/`` is the exception to "nothing is invoked directly": its
three audits are what ``apexwms verify-*`` runs, hand-wired by the CLI
because there is no request to resolve them in.
"""

from application.services.claims import ClaimsFactory
from application.services.cost_pools import CostPoolReader
from application.services.count_posting import CountPoster
from application.services.device_unit_loader import DeviceUnitLoader
from application.services.device_unit_repricer import DeviceUnitRepricer
from application.services.document_lines import DocumentLineBuilder
from application.services.document_loader import DocumentLoader
from application.services.document_numbering import DocumentNumberer
from application.services.invoice_posting import InvoicePoster
from application.services.ledger import LedgerPoster
from application.services.payment_posting import PaymentPoster
from application.services.product_repricer import ProductRepricer
from application.services.receipt_posting import ReceiptPoster
from application.services.removal_posting import RemovalPoster
from application.services.removal_scanning import RemovalScanner
from application.services.sale_price import SalePriceParser
from application.services.slugs import SlugNormalizer
from application.services.timezones import TimezoneValidator
from application.services.token_issuer import TokenIssuer
from application.services.verification import (
    BalanceVerifier,
    LedgerReconciler,
    ProjectionVerifier,
)

__all__ = [
    "BalanceVerifier",
    "ClaimsFactory",
    "CostPoolReader",
    "CountPoster",
    "DeviceUnitLoader",
    "DeviceUnitRepricer",
    "DocumentLineBuilder",
    "DocumentLoader",
    "DocumentNumberer",
    "InvoicePoster",
    "LedgerPoster",
    "LedgerReconciler",
    "PaymentPoster",
    "ProductRepricer",
    "ProjectionVerifier",
    "ReceiptPoster",
    "RemovalPoster",
    "RemovalScanner",
    "SalePriceParser",
    "SlugNormalizer",
    "TimezoneValidator",
    "TokenIssuer",
]
