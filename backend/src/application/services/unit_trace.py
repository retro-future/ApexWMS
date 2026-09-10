"""FR-9.2: one handset's whole life, merged from three append-only sources.

The stock ledger says what happened to the goods, the price log says what
the store asked for them, and the invoice line says what a customer paid.
None of the three is ever edited, so the timeline is a read.

The two enrichments attach by document id rather than by timestamp: a
``RECEIPT`` movement names the goods receipt whose origin it wants, and a
``SALE`` movement names the invoice whose prices it wants. A handset sold,
cancelled and sold again therefore lands each price on its own sale with
nothing to guess about.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.common.specification import Specification
from application.dtos import (
    LedgerActor,
    MovementLogRow,
    TraceEvent,
    TraceEventKind,
    UnitSale,
)
from application.ports import (
    GoodsReceiptQueries,
    SalesInvoiceQueries,
    StockMovementQueries,
)
from application.specs import PriceChangesForUnit
from domain.entities import DeviceUnitPriceChange, Employee
from domain.enums import DocumentType, MovementType
from infrastructure.persistence.tenant.models import (
    DeviceUnitPriceChangeModel,
    EmployeeModel,
)

# Exhaustive by assertion, not by hope: a new ``MovementType`` that nobody
# maps here would otherwise take out the whole timeline of every handset it
# touched, and only at read time. M6 added ``CUSTOMER_RETURN`` and this table
# did not follow.
_OF_MOVEMENT: dict[MovementType, TraceEventKind] = {
    MovementType.RECEIPT: TraceEventKind.RECEIVED,
    MovementType.SALE: TraceEventKind.SOLD,
    MovementType.CUSTOMER_RETURN: TraceEventKind.RETURNED_BY_CUSTOMER,
    MovementType.SUPPLIER_RETURN: TraceEventKind.RETURNED_TO_SUPPLIER,
    MovementType.WRITE_OFF: TraceEventKind.WRITTEN_OFF,
    MovementType.COUNT_ADJUSTMENT: TraceEventKind.COUNT_ADJUSTMENT,
}

assert set(_OF_MOVEMENT) == set(MovementType), (
    "every MovementType needs a TraceEventKind: "
    f"{set(MovementType) - set(_OF_MOVEMENT)} unmapped"
)


class UnitTraceAssembler:
    def __init__(
        self,
        movements: StockMovementQueries,
        prices: TenantAppendOnlyRepository[
            DeviceUnitPriceChange, DeviceUnitPriceChangeModel
        ],
        receipts: GoodsReceiptQueries,
        sales: SalesInvoiceQueries,
        employees: TenantDbRepository[Employee, EmployeeModel],
    ) -> None:
        self._movements = movements
        self._prices = prices
        self._receipts = receipts
        self._sales = sales
        self._employees = employees

    async def events(self, device_unit_id: UUID) -> list[TraceEvent]:
        moved = await self._movements.trace_for_unit(device_unit_id)
        sales = await self._sales.sales_of_unit(device_unit_id)
        roster = Specification(EmployeeModel).order(
            EmployeeModel.created_at, EmployeeModel.id
        )
        names = {one.id: one.full_name for one in await self._employees.find(roster)}

        events = [await self._from_movement(row, sales) for row in moved]
        events.extend(await self._pricings(device_unit_id, names))
        # Intake and its pricing share one instant (``ReceiptPoster`` passes
        # it in), so the tiebreak decides which reads first — and a handset
        # is received before anyone prices it.
        return sorted(
            events,
            key=lambda event: (
                event.occurred_at,
                0 if event.kind is TraceEventKind.RECEIVED else 1,
            ),
        )

    async def _from_movement(
        self, row: MovementLogRow, sales: dict[UUID, UnitSale]
    ) -> TraceEvent:
        origin = None
        if row.document_type is DocumentType.GOODS_RECEIPT:
            origin = await self._receipts.origin_of(row.document_id)
        return TraceEvent(
            kind=_OF_MOVEMENT[row.movement_type],
            occurred_at=row.occurred_at,
            actor=row.actor,
            note=row.note,
            document_type=row.document_type,
            document_id=row.document_id,
            document_number=row.document_number,
            location_id=row.location_id,
            location_name=row.location_name,
            origin=origin,
            sale=sales.get(row.document_id),
        )

    async def _pricings(
        self, device_unit_id: UUID, names: dict[UUID, str]
    ) -> list[TraceEvent]:
        return [
            TraceEvent(
                kind=TraceEventKind.PRICED,
                occurred_at=change.occurred_at,
                actor=LedgerActor(
                    user_id=change.user_id, user_name=names.get(change.user_id)
                ),
                note=change.reason,
                old_price=change.old_price,
                new_price=change.new_price,
            )
            for change in await self._prices.find(PriceChangesForUnit(device_unit_id))
        ]
