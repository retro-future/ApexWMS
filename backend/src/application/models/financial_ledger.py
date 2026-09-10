"""One row of the financial ledger — FR-10.3, PRD §5.10.

Every row carries its own currency, because this is the one table where a
som payment and a dollar sale sit next to each other (§4.6). There is
deliberately no total field on the report this belongs to: a single figure
over these rows would be adding the two together.

The whole route is behind ``Permission.FinancialLedger.View``, so there is
no per-field omission here — a reader who reaches this sees the money.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import FinancialLedgerRow
from application.models.money import MoneyData
from domain.enums import DocumentType, TransactionType


class FinancialLedgerRowData(CamelModel):
    id: UUID
    occurred_at: datetime
    txn_type: TransactionType
    # Signed, per §4.6's convention: negative is money out.
    amount: MoneyData
    product_id: UUID | None
    product_name: str | None
    device_unit_id: UUID | None
    imei: str | None
    location_id: UUID | None
    location_name: str | None
    document_type: DocumentType
    document_id: UUID
    document_number: str | None
    user_id: UUID
    user_name: str | None
    note: str | None

    @classmethod
    def from_entity(cls, row: FinancialLedgerRow) -> FinancialLedgerRowData:
        return cls(
            id=row.id,
            occurred_at=row.occurred_at,
            txn_type=row.txn_type,
            amount=MoneyData.from_entity(row.amount),
            product_id=row.product_id,
            product_name=row.product_name,
            device_unit_id=row.device_unit_id,
            imei=row.imei,
            location_id=row.location_id,
            location_name=row.location_name,
            document_type=row.document_type,
            document_id=row.document_id,
            document_number=row.document_number,
            user_id=row.actor.user_id,
            user_name=row.actor.user_name,
            note=row.note,
        )
