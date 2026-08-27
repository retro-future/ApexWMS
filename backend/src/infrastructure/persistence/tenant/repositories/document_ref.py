"""Turning a ledger row's ``(document_type, document_id)`` into its number.

Both ledgers name their cause by that pair rather than a foreign key,
because six tables can be the cause and a column cannot point at six
(§4.3). The movement log and the financial ledger both have to show the
number an operator would recognise, so the resolution is written once here
rather than twice in two repositories.

A ``CASE`` over correlated subqueries rather than six outer joins: Postgres
evaluates only the branch that matches, so a row costs one lookup instead
of six. ``DocumentType.PAYMENT`` is deliberately absent — a payment has no
number to show (§4.7).
"""

from uuid import UUID

from sqlalchemy import ColumnElement, case, select
from sqlalchemy.orm import InstrumentedAttribute

from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import (
    GoodsReceiptModel,
    PurchaseOrderModel,
    SalesInvoiceModel,
    StockCountModel,
    SupplierReturnModel,
    WriteOffModel,
)

_NUMBERED = {
    DocumentType.PURCHASE_ORDER: PurchaseOrderModel,
    DocumentType.GOODS_RECEIPT: GoodsReceiptModel,
    DocumentType.SALES_INVOICE: SalesInvoiceModel,
    DocumentType.SUPPLIER_RETURN: SupplierReturnModel,
    DocumentType.WRITE_OFF: WriteOffModel,
    DocumentType.STOCK_COUNT: StockCountModel,
}


def document_number(
    document_type: InstrumentedAttribute[str],
    document_id: InstrumentedAttribute[UUID],
) -> ColumnElement[str | None]:
    """The number of the document that caused this row, or null."""
    return case(
        *(
            (
                document_type == kind.value,
                select(model.number).where(model.id == document_id).scalar_subquery(),
            )
            for kind, model in _NUMBERED.items()
        ),
        else_=None,
    )
