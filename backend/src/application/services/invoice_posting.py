"""Turning a confirmed Sales Invoice into a sale (PRD §5.4, FR-4.6).

The outbound mirror of ``ReceiptPoster``, and the place where **the price
is resolved for the second time** (FR-4.5b1). ``SalesInvoice.confirm()``
has checked what lives on the aggregate; everything that needs the live
unit and the live catalog row is here, because a draft can sit open for
hours while prices and stock move underneath it.

Per line, in this order and for a reason:

1. The goods are re-checked. A handset still has to be ``IN_STOCK`` at the
   invoice's location (FR-4.3, FR-4.4) — the scan checked it, but two
   drafts can hold the same phone and a draft reserves nothing. An
   accessory line is checked against the level, whole (FR-4.7): there is no
   partial fulfilment.
2. The price is resolved again through ``PriceResolver``, the same function
   the scan ran, which is what stops a draft and its confirm from
   disagreeing about the rule. A line that has stopped resolving — its unit
   was flipped to ``USED`` while the draft sat open — raises
   ``PriceNotSetError`` here (FR-4.5b2).
3. The line snapshots what was resolved and what is charged (FR-4.5b). An
   explicit override survives; everything else takes the fresh figure, so a
   markdown made while the draft was open reaches the customer.
4. Both ledgers are written by ``LedgerPoster``: ``SALE_REVENUE`` from the
   snapshot and ``COGS`` against the same movement, together or not at all.

COGS follows §4.6's two rules. A phone costs what *that* phone cost —
specific identification, a fact rather than a model. An accessory costs its
share of a weighted-average pool replayed from the ledger
(``CostPoolReader``), which is the same figure ``verify-financials``
reconciles against.

Nothing here commits. The handler owns the transaction, which is what makes
FR-4.5b2's "nothing is written to either ledger" true: a tenth line that
will not resolve rolls back the nine before it.
"""

from application.dtos import MoneyEffect, Posting, PostingEntry
from application.errors import NotFoundError
from application.ports import DeviceUnitRepository, ProductRepository, StockLevelRepository
from application.services.cost_pools import CostPoolReader
from application.services.ledger import LedgerPoster
from domain.entities import DeviceUnit, Product, SalesInvoice, SalesInvoiceLine
from domain.enums import DeviceStatus, DocumentType, MovementType, TransactionType
from domain.errors import InsufficientStockError, UnitNotSellableError, WrongLocationError
from domain.services import PriceResolver
from domain.value_objects import Money


class InvoicePoster:
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

    async def sell(self, invoice: SalesInvoice) -> None:
        entries: list[PostingEntry] = []
        for line in invoice.lines:
            if line.is_serial:
                entries.append(await self._serial_entry(invoice, line))
            else:
                entries.append(await self._quantity_entry(invoice, line))

        await self._poster.post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=invoice.id,
                entries=entries,
            )
        )

    async def _serial_entry(
        self, invoice: SalesInvoice, line: SalesInvoiceLine
    ) -> PostingEntry:
        unit = await self._load_unit(line)
        product = await self._load_product(line)
        self._assert_sellable(invoice, unit)

        line.snapshot(PriceResolver.resolve(unit, product))
        revenue = line.line_total
        assert revenue is not None

        return PostingEntry(
            movement_type=MovementType.SALE,
            product_id=line.product_id,
            location_id=invoice.location_id,
            quantity_delta=-1,
            device_unit_id=unit.id,
            new_status=DeviceStatus.SOLD,
            # A sold unit has left the store, so it holds no location —
            # ``DeviceUnit.__post_init__`` refuses the alternative.
            new_location_id=None,
            money=[
                MoneyEffect(TransactionType.SALE_REVENUE, revenue),
                # Specific identification: this phone's own cost, not a
                # model of what phones like it cost (§4.6).
                MoneyEffect(TransactionType.COGS, -unit.acquisition_cost),
            ],
        )

    async def _quantity_entry(
        self, invoice: SalesInvoice, line: SalesInvoiceLine
    ) -> PostingEntry:
        product = await self._load_product(line)
        await self._assert_in_stock(invoice, line, str(product.sku))

        line.snapshot(PriceResolver.resolve(None, product))
        revenue = line.line_total
        assert revenue is not None

        return PostingEntry(
            movement_type=MovementType.SALE,
            product_id=line.product_id,
            location_id=invoice.location_id,
            quantity_delta=-line.quantity,
            money=[
                MoneyEffect(TransactionType.SALE_REVENUE, revenue),
                MoneyEffect(TransactionType.COGS, -await self._cogs_for(invoice, line)),
            ],
        )

    async def _cogs_for(self, invoice: SalesInvoice, line: SalesInvoiceLine) -> Money:
        """This line's share of the weighted-average pool (§4.6).

        The pool is replayed rather than read from a column, so the figure
        booked here is by construction the one ``verify-financials``
        recomputes.
        """
        pool = await self._pools.pool_for(line.product_id, invoice.location_id)
        if pool is None:
            raise NotFoundError(f"product {line.product_id} does not exist in this store")
        _, cost = pool.issue(line.quantity)
        return cost

    async def _load_unit(self, line: SalesInvoiceLine) -> DeviceUnit:
        assert line.device_unit_id is not None
        unit = await self._units.get(line.device_unit_id)
        if unit is None:
            raise NotFoundError(f"handset {line.device_unit_id} does not exist in this store")
        return unit

    async def _load_product(self, line: SalesInvoiceLine) -> Product:
        product = await self._products.get(line.product_id)
        if product is None:
            raise NotFoundError(f"product {line.product_id} does not exist in this store")
        return product

    @staticmethod
    def _assert_sellable(invoice: SalesInvoice, unit: DeviceUnit) -> None:
        """Re-checked at confirm because a draft reserves nothing (§4.4)."""
        if unit.status is not DeviceStatus.IN_STOCK:
            raise UnitNotSellableError(
                f"IMEI {unit.imei} is {unit.status.value} and can no longer be sold"
            )
        if unit.location_id != invoice.location_id:
            raise WrongLocationError(
                f"IMEI {unit.imei} has moved and is no longer held at "
                f"{invoice.number}'s location"
            )

    async def _assert_in_stock(
        self, invoice: SalesInvoice, line: SalesInvoiceLine, sku: str
    ) -> None:
        level = await self._levels.get_for(line.product_id, invoice.location_id)
        on_hand = 0 if level is None else level.quantity
        if on_hand < line.quantity:
            raise InsufficientStockError(
                f"{invoice.number} sells {line.quantity} of {sku} but only {on_hand} "
                "are here — there is no partial fulfilment (FR-4.7)"
            )
