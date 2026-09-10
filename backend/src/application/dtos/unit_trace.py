"""One handset's whole life, in order — FR-9.2, PRD §5.9.

*"Bought, priced, cut twice, sold below asking, with the name of whoever
approved that."* Three append-only sources make that one timeline: the
stock ledger, the unit's price log, and the invoice line that sold it. None
of them is edited, so the trace is a read and never a reconstruction.

One flat ``TraceEvent`` with a ``kind`` rather than a class per event: the
optional halves are what each kind carries, and the timeline is sorted and
rendered as one list. Every field on it is a fact some row holds.

**There is no condition-change event.** Changing a unit's condition
(FR-2.18) writes a projection and no log, so the trace would have to invent
its date. A timeline that guesses is worse than one that is missing a line.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from application.dtos.ledger_log import LedgerActor
from domain.entities import DeviceUnit, Product
from domain.enums import AcquisitionSource, DocumentType
from domain.value_objects import Money


class TraceEventKind(StrEnum):
    RECEIVED = "received"
    PRICED = "priced"
    SOLD = "sold"
    RETURNED_BY_CUSTOMER = "returned_by_customer"
    RETURNED_TO_SUPPLIER = "returned_to_supplier"
    WRITTEN_OFF = "written_off"
    COUNT_ADJUSTMENT = "count_adjustment"


@dataclass(frozen=True, slots=True)
class UnitOrigin:
    """Where the handset came from — a supplier, or a walk-in (FR-3.3b)."""

    acquisition_source: AcquisitionSource
    supplier_id: UUID | None
    supplier_name: str | None
    customer_id: UUID | None
    customer_name: str | None


@dataclass(frozen=True, slots=True)
class UnitSale:
    """The line that sold it, with both prices and who approved the gap.

    ``resolved_price`` is what the system worked out at confirm and
    ``charged_price`` is what the customer paid (FR-4.5f). They are equal on
    most lines; where they are not, ``price_approved_by_name`` is the whole
    point of the report.
    """

    invoice_id: UUID
    invoice_number: str
    customer_id: UUID | None
    customer_name: str | None
    resolved_price: Money | None
    charged_price: Money | None
    price_approved_by: UUID | None
    price_approved_by_name: str | None
    price_note: str | None


@dataclass(frozen=True, slots=True)
class TraceEvent:
    kind: TraceEventKind
    occurred_at: datetime
    actor: LedgerActor
    note: str | None = None
    document_type: DocumentType | None = None
    document_id: UUID | None = None
    document_number: str | None = None
    location_id: UUID | None = None
    location_name: str | None = None
    # PRICED only. ``old_price`` is null for the first pricing (FR-2.15).
    old_price: Money | None = None
    new_price: Money | None = None
    # RECEIVED only.
    origin: UnitOrigin | None = None
    # SOLD only.
    sale: UnitSale | None = None


@dataclass(frozen=True, slots=True)
class UnitTrace:
    unit: DeviceUnit
    product: Product
    events: list[TraceEvent]
