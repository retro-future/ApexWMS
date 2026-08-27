"""FR-10.3: the raw money ledger, mirroring the movement log.

Behind ``Permission.FinancialLedger.View`` rather than ``Reporting.View``,
which is what that permission was catalogued for: §2.1 grades *"what did we
move"* and *"what did we earn"* as different questions even though the same
two roles hold both today.
"""

from datetime import datetime
from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import FinancialLedgerRowData
from application.ports import FinancialTransactionRepository
from domain.enums import DocumentType, TransactionType


class ListFinancialLedgerQuery(PagedQuery[PagedResult[FinancialLedgerRowData]]):
    from_date: datetime | None = None
    to_date: datetime | None = None
    txn_type: TransactionType | None = None
    location_id: UUID | None = None
    document_type: DocumentType | None = None


class ListFinancialLedgerHandler(
    IRequestHandler[PagedResult[FinancialLedgerRowData], ListFinancialLedgerQuery]
):
    def __init__(self, transactions: FinancialTransactionRepository) -> None:
        self._transactions = transactions

    async def handle(
        self, request: ListFinancialLedgerQuery
    ) -> PagedResult[FinancialLedgerRowData]:
        rows, total = await self._transactions.list_page(
            page=request.page,
            page_size=request.page_size,
            from_date=request.from_date,
            to_date=request.to_date,
            txn_type=request.txn_type,
            location_id=request.location_id,
            document_type=request.document_type,
        )
        return PagedResult[FinancialLedgerRowData].succeed_with_data(
            data=[FinancialLedgerRowData.from_entity(row) for row in rows],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
