"""Turning a confirmed Goods Receipt into stock (PRD §5.3, FR-3.7).

The receipt has already decided everything by the time it gets here:
``GoodsReceipt.confirm()`` has counted the scans, refused the unpriced used
handsets and fixed the document. What is left is mechanical, and it is
collected in one place because getting any part of it wrong is invisible
until a month-end report disagrees with the shelf.

Three things happen per scanned handset, in this order and for a reason:

1. The IMEI is checked against the rest of the store. The scan endpoint
   checked it too, but two receipts can be open at once and the phone can
   be scanned onto both between them — this is the check that actually
   holds (FR-3.5).
2. The ``DeviceUnit`` is created, then its intake price is written
   **through the repricer**, so the unit's markdown log starts at its first
   moment with ``old_price = NULL`` (FR-3.11) instead of the projection
   being seeded behind the log's back.
3. Both ledgers are written by ``LedgerPoster``, together or not at all.

Nothing here commits. The handler owns the transaction, so a duplicate
IMEI found on the tenth phone rolls back the nine before it.
"""

from datetime import datetime

from application.dtos import MoneyEffect, Posting, PostingEntry
from application.errors import DuplicateImeiError
from application.ports import Clock, DeviceUnitRepository
from application.services.device_unit_repricer import DeviceUnitRepricer
from application.services.ledger import LedgerPoster
from domain.entities import DeviceUnit, GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.enums import DeviceStatus, DocumentType, MovementType, TransactionType


class ReceiptPoster:
    def __init__(
        self,
        units: DeviceUnitRepository,
        repricer: DeviceUnitRepricer,
        poster: LedgerPoster,
        clock: Clock,
    ) -> None:
        self._units = units
        self._repricer = repricer
        self._poster = poster
        self._clock = clock

    async def receive(self, receipt: GoodsReceipt) -> None:
        now = self._clock.now()
        entries: list[PostingEntry] = []

        for line in receipt.lines:
            if line.is_serial:
                for scanned in line.units:
                    unit = await self._create_unit(receipt, line, scanned, now)
                    entries.append(self._serial_entry(receipt, line, unit))
            else:
                entries.append(self._quantity_entry(receipt, line))

        await self._poster.post(
            Posting(
                document_type=DocumentType.GOODS_RECEIPT,
                document_id=receipt.id,
                entries=entries,
            )
        )

    async def _create_unit(
        self,
        receipt: GoodsReceipt,
        line: GoodsReceiptLine,
        scanned: ReceivedUnit,
        now: datetime,
    ) -> DeviceUnit:
        await self._assert_imei_is_free(scanned)

        # ``confirm()`` has already refused a scan without a cost, so the
        # assertion documents that rather than handling a real case.
        assert scanned.acquisition_cost is not None

        unit = DeviceUnit(
            imei=scanned.imei,
            imei2=scanned.imei2,
            serial_number=scanned.serial_number,
            product_id=line.product_id,
            status=DeviceStatus.IN_STOCK,
            location_id=receipt.location_id,
            acquisition_cost=scanned.acquisition_cost,
            condition=scanned.condition,
            cash_paid_minor=scanned.cash_paid_minor,
            cash_paid_currency=scanned.cash_paid_currency,
            source_document_type=DocumentType.GOODS_RECEIPT,
            source_document_id=receipt.id,
            created_at=now,
        )
        # Added before pricing because the price-change row's foreign key
        # points at this unit.
        await self._units.add(unit)

        if scanned.asking_price is not None:
            await self._repricer.set_price(unit, scanned.asking_price, "priced at intake")
            await self._units.update(unit)
        return unit

    async def _assert_imei_is_free(self, scanned: ReceivedUnit) -> None:
        existing = await self._units.get_by_imei(str(scanned.imei))
        if existing is None:
            return
        raise DuplicateImeiError(
            f"IMEI {scanned.imei} is already in this store: {existing.status.value}"
            + (f" at location {existing.location_id}" if existing.location_id else "")
        )

    @staticmethod
    def _serial_entry(
        receipt: GoodsReceipt, line: GoodsReceiptLine, unit: DeviceUnit
    ) -> PostingEntry:
        return PostingEntry(
            movement_type=MovementType.RECEIPT,
            product_id=line.product_id,
            location_id=receipt.location_id,
            quantity_delta=1,
            device_unit_id=unit.id,
            new_status=DeviceStatus.IN_STOCK,
            new_location_id=receipt.location_id,
            # Booked at what the owner stated in the product's currency. The
            # som handed over for a trade-in rides along on the unit and
            # enters nothing here (§4.5b, FR-3.4d).
            money=[MoneyEffect(TransactionType.PURCHASE, -unit.acquisition_cost)],
        )

    @staticmethod
    def _quantity_entry(receipt: GoodsReceipt, line: GoodsReceiptLine) -> PostingEntry:
        total = line.total_cost
        assert total is not None
        return PostingEntry(
            movement_type=MovementType.RECEIPT,
            product_id=line.product_id,
            location_id=receipt.location_id,
            quantity_delta=line.quantity,
            # The whole line as one figure, which is the form
            # ``CostPool.receive_total`` consumes: dividing it out per unit
            # and multiplying back would introduce a rounding error that was
            # never in the data.
            money=[MoneyEffect(TransactionType.PURCHASE, -total)],
        )
