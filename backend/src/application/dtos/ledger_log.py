"""The two raw ledger reads — FR-9.5 and FR-10.3, PRD §5.9, §5.10.

One module for both, because they are the same shape twice: a ledger row
flattened with the names an operator recognises, rather than the ids it
stores. Neither carries a total. A log's job is to show what happened, and
a figure summed across the currencies these rows mix would be wrong the
moment a som payment sat next to a dollar sale (§4.5 rule 4).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.enums import DocumentType, MovementType, TransactionType
from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class LedgerActor:
    """Who caused the row, by name as well as by id.

    ``Employee.id`` *is* the platform ``User.id`` (§3.1), so this is a plain
    join inside the tenant database and not a second lookup elsewhere.
    """

    user_id: UUID
    user_name: str | None


@dataclass(frozen=True, slots=True)
class MovementLogRow:
    id: UUID
    occurred_at: datetime
    movement_type: MovementType
    # Signed. A reversal keeps its type and flips this (§4.3 rule 3), which
    # is why the log never has a category to exclude.
    quantity_delta: int
    product_id: UUID
    sku: str
    product_name: str
    device_unit_id: UUID | None
    imei: str | None
    location_id: UUID
    location_name: str
    document_type: DocumentType
    document_id: UUID
    document_number: str | None
    actor: LedgerActor
    note: str | None


@dataclass(frozen=True, slots=True)
class FinancialLedgerRow:
    id: UUID
    occurred_at: datetime
    txn_type: TransactionType
    # Signed, and in its own currency — the one ledger row that carries one
    # (§4.6), because a payment need not match its invoice's lines.
    amount: Money
    product_id: UUID | None
    product_name: str | None
    device_unit_id: UUID | None
    imei: str | None
    location_id: UUID | None
    location_name: str | None
    document_type: DocumentType
    document_id: UUID
    document_number: str | None
    actor: LedgerActor
    note: str | None
