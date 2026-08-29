"""Whole-row reads of the money ledger (§4.6). Written against
``FinancialTransactionModel`` (ADR 0007).

The aggregate reads (the FR-10.3 log, ``sales_totals``, ``totals_by_type``)
group by currency and return read-model rows or a dict, so they live in
``FinancialTransactionQueries`` (`query-services.md`). Each spec stores its
filters as plain attributes for the in-memory fake.
"""

from uuid import UUID

from application.common.specification import Specification
from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import FinancialTransactionModel


class TransactionsForDocument(Specification[FinancialTransactionModel]):
    """Everything one document booked — what a cancellation reverses."""

    def __init__(self, document_type: DocumentType, document_id: UUID) -> None:
        super().__init__(FinancialTransactionModel)
        self.document_type = document_type
        self.document_id = document_id
        self.where(
            FinancialTransactionModel.document_type == document_type.value,
            FinancialTransactionModel.document_id == document_id,
        )
        self.order(FinancialTransactionModel.occurred_at, FinancialTransactionModel.id)


class TransactionsForPair(Specification[FinancialTransactionModel]):
    """What one product cost at one location, in order — replayed alongside
    the stock movements to check a COGS booked at the wrong average (§4.6)."""

    def __init__(self, product_id: UUID, location_id: UUID) -> None:
        super().__init__(FinancialTransactionModel)
        self.product_id = product_id
        self.location_id = location_id
        self.where(
            FinancialTransactionModel.product_id == product_id,
            FinancialTransactionModel.location_id == location_id,
            FinancialTransactionModel.device_unit_id.is_(None),
        )
        self.order(FinancialTransactionModel.occurred_at, FinancialTransactionModel.id)
