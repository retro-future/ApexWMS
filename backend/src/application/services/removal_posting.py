"""Taking goods off the shelf for good (PRD §5.5, §5.6, FR-5.3, FR-6.5).

A Supplier Return and a Write-Off are the same act with a different label
on the money: stock leaves at its book value, nothing is sold, and no
revenue is booked. So the mechanics live here once and the two documents
enter through their own named method, rather than as two services that
would drift apart the first time one of them was fixed.

What differs between them is three values — the movement type, where the
handset lands, and which financial category carries the amount — and the
*sign* is not a fourth. ``TransactionType.ordinary_sign`` already states
which way each category points when first booked (§4.6): a return credit is
positive, a write-off loss negative. Reading it from the enum is what stops
this service from holding a second opinion about §4.6's sign convention.

Per line, in this order and for a reason:

1. The goods are re-checked against the live store. A handset still has to
   be ``IN_STOCK`` at the document's location (FR-5.2) — the scan checked
   it, but a draft reserves nothing and the phone can be sold from under it.
   An accessory line is checked against the level, whole: half a confirmed
   write-off is a document the ledgers could not describe.
2. The line is valued at what the goods are carried at (§4.6): a phone's
   own ``acquisition_cost``, an accessory's share of the weighted-average
   pool replayed from the ledger.
3. Both ledgers are written by ``LedgerPoster``, together or not at all.

Nothing here commits. The handler owns the transaction, so a handset found
sold on the tenth line rolls back the nine before it.
"""


from application.dtos import MoneyEffect, Posting, PostingEntry
from application.errors import NotFoundError
from application.ports import DeviceUnitRepository, ProductRepository, StockLevelRepository
from application.services.cost_pools import CostPoolReader
from application.services.ledger import LedgerPoster
from domain.entities import RemovalLine, SupplierReturn, WriteOff
from domain.enums import DeviceStatus, DocumentType, MovementType, TransactionType
from domain.errors import InsufficientStockError, UnitNotRemovableError, WrongLocationError
from domain.value_objects import Money


class RemovalPoster:
    def __init__(
        self,
        units: DeviceUnitRepository,
        products: ProductRepository,
        levels: StockLevelRepository,
        pools: CostPoolReader,
        poster: LedgerPoster,
    ) -> None:
        self._units = units
        self._products = products
        self._levels = levels
        self._pools = pools
        self._poster = poster

    async def send_back(self, document: SupplierReturn) -> None:
        """FR-5.3: goods go back to the supplier and the store is credited."""
        await self._post(
            document_type=DocumentType.SUPPLIER_RETURN,
            document=document,
            movement_type=MovementType.SUPPLIER_RETURN,
            new_status=DeviceStatus.RETURNED_TO_SUPPLIER,
            txn_type=TransactionType.SUPPLIER_RETURN_CREDIT,
        )

    async def write_off(self, document: WriteOff) -> None:
        """FR-6.5: goods are gone and the store absorbs their book value."""
        await self._post(
            document_type=DocumentType.WRITE_OFF,
            document=document,
            movement_type=MovementType.WRITE_OFF,
            new_status=DeviceStatus.WRITTEN_OFF,
            txn_type=TransactionType.WRITE_OFF_LOSS,
        )

    async def _post(
        self,
        *,
        document_type: DocumentType,
        document: SupplierReturn | WriteOff,
        movement_type: MovementType,
        new_status: DeviceStatus,
        txn_type: TransactionType,
    ) -> None:
        entries: list[PostingEntry] = []
        for line in document.lines:
            value = await self._book_value(document, line)
            entries.append(
                PostingEntry(
                    movement_type=movement_type,
                    product_id=line.product_id,
                    location_id=document.location_id,
                    quantity_delta=-line.quantity,
                    device_unit_id=line.device_unit_id,
                    # Stated by the caller and not inferred: only the
                    # document knows whether a ``-1`` means returned or
                    # written off (§4.3).
                    new_status=new_status if line.is_serial else None,
                    # Either way the unit has left the store, so it holds no
                    # location — ``DeviceUnit.__post_init__`` refuses the
                    # alternative.
                    new_location_id=None,
                    money=[MoneyEffect(txn_type, value * txn_type.ordinary_sign)],
                )
            )

        await self._poster.post(
            Posting(
                document_type=document_type, document_id=document.id, entries=entries
            )
        )

    async def _book_value(
        self, document: SupplierReturn | WriteOff, line: RemovalLine
    ) -> Money:
        """What the goods on this line are carried at, unsigned (§4.6)."""
        if line.is_serial:
            return await self._serial_value(document, line)
        await self._assert_in_stock(document, line)
        return await self._pools.issue_value(
            line.product_id, document.location_id, line.quantity
        )

    async def _serial_value(
        self, document: SupplierReturn | WriteOff, line: RemovalLine
    ) -> Money:
        assert line.device_unit_id is not None
        unit = await self._units.get(line.device_unit_id)
        if unit is None:
            raise NotFoundError(
                f"handset {line.device_unit_id} does not exist in this store"
            )
        # Re-checked at confirm because a draft reserves nothing (§4.4).
        if unit.status is not DeviceStatus.IN_STOCK:
            raise UnitNotRemovableError(
                f"IMEI {unit.imei} is {unit.status.value} and is no longer on the "
                f"shelf, so {document.number} cannot move it (FR-5.2)"
            )
        if unit.location_id != document.location_id:
            raise WrongLocationError(
                f"IMEI {unit.imei} has moved and is no longer held at "
                f"{document.number}'s location"
            )
        # Specific identification: this phone's own cost, not a model of
        # what phones like it cost (§4.6).
        return unit.acquisition_cost

    async def _assert_in_stock(
        self, document: SupplierReturn | WriteOff, line: RemovalLine
    ) -> None:
        product = await self._products.get(line.product_id)
        if product is None:
            raise NotFoundError(f"product {line.product_id} does not exist in this store")

        level = await self._levels.get_for(line.product_id, document.location_id)
        on_hand = 0 if level is None else level.quantity
        if on_hand < line.quantity:
            raise InsufficientStockError(
                f"{document.number} moves {line.quantity} of {product.sku} but only "
                f"{on_hand} are here — there is no partial fulfilment"
            )
