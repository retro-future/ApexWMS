"""The six documents, all sharing one lifecycle (PRD §4.4).

Every ledger row names its cause as ``(document_type, document_id)``, and
this is the vocabulary of that first half. The pair is what makes
cancellation possible without deletion: "find everything document X
wrote, and write its opposite" is a query.

``PURCHASE_ORDER`` appears here for completeness even though confirming
one moves neither goods nor money — a PO is an intention to buy (§4.4), so
it never appears in either ledger.
"""

from enum import StrEnum


class DocumentType(StrEnum):
    PURCHASE_ORDER = "purchase_order"
    GOODS_RECEIPT = "goods_receipt"
    SALES_INVOICE = "sales_invoice"
    SUPPLIER_RETURN = "supplier_return"
    STOCK_COUNT = "stock_count"
    WRITE_OFF = "write_off"
