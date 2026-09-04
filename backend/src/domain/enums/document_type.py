"""What caused a ledger row (PRD §4.4, §4.7).

Every ledger row names its cause as ``(document_type, document_id)``, and
this is the vocabulary of that first half. The pair is what makes
cancellation possible without deletion: "find everything document X
wrote, and write its opposite" is a query.

``PURCHASE_ORDER`` appears here for completeness even though confirming
one moves neither goods nor money — a PO is an intention to buy (§4.4), so
it never appears in either ledger.

``PAYMENT`` is the one member that is not a ``Document``: a payment has no
``DRAFT → CONFIRMED`` lifecycle and no lines. It is here because a payment
*is* a cause, and giving it its own identity is what keeps cancelling a
store-credit invoice from reversing the money the customer already handed
over (FR-11.11). Booking payments under the invoice would put them inside
``LedgerPoster.reverse``'s blast radius, answerable only by a category
carve-out inside the one service that must not have one.
"""

from enum import StrEnum


class DocumentType(StrEnum):
    PURCHASE_ORDER = "purchase_order"
    GOODS_RECEIPT = "goods_receipt"
    SALES_INVOICE = "sales_invoice"
    SUPPLIER_RETURN = "supplier_return"
    CUSTOMER_RETURN = "customer_return"
    STOCK_COUNT = "stock_count"
    WRITE_OFF = "write_off"
    PAYMENT = "payment"
