"""Making the books agree with the shelf (PRD §5.6, FR-6.4).

``StockCount.confirm()`` has checked what lives on the aggregate: that the
count was closed, and that every surprise handset names a product and a
cost. What is left needs the live store, so it is here — the same split
``GoodsReceipt`` and ``SalesInvoice`` both keep.

**Everything here adjusts what the ledger gets wrong *now*, not what a row
is labelled.** The snapshot froze the books when the count opened, and the
store kept trading while somebody walked the aisles — so a row's label and
the live ledger routinely disagree, and posting the label would re-book
whatever happened in between. Each case below says which figure it trusts,
and each of those choices is a bug someone would otherwise write.

- **Matched** writes nothing at all. The books were right; there is no
  event. A movement of zero would be a row asserting that something
  happened.
- **Missing** takes the handset off the shelf at its own cost — *unless it
  has already left through a documented path*. One sold while the count sat
  open is not missing, it is sold. The movement is ``COUNT_ADJUSTMENT`` and
  not ``WRITE_OFF``, even though the unit lands in the same ``WRITTEN_OFF``
  status (``domain/services/projection.py``): "we looked and it was gone"
  and "we know it was stolen" are different claims, and §5.10 reports them
  in different columns.
- **Unexpected** brings it on at the location the count names, and books
  money only if the store was not already holding it — a phone found on
  another shelf is a location correction, not a change in value. A genuine
  surprise has no row anywhere, so confirming is what creates the
  ``DeviceUnit``, with the cost somebody stated, no asking price, and
  ``USED`` (FR-6.4b, and see ``domain/entities/stock_count.py`` for why the
  condition is not a choice).
- **Quantity lines** adjust against the **live level**, valued at the pool.
  ``StockCountLine.delta`` is the report figure and is not what gets
  posted.

**The sign is computed here and not read from the enum.**
``TransactionType.COUNT_ADJUSTMENT.ordinary_sign`` is deliberately ``0``
(§4.6): a count finds surplus as readily as shortage and neither is the
exceptional case, so the direction comes from what was actually found.

Nothing here commits. The handler owns the transaction, so a surplus that
cannot be valued on the fortieth line rolls back the thirty-nine before it.
"""

from datetime import datetime

from application.dtos import MoneyEffect, Posting, PostingEntry
from application.errors import NotFoundError
from application.ports import (
    Clock,
    DeviceUnitRepository,
    ProductRepository,
    StockLevelRepository,
)
from application.services.cost_pools import CostPoolReader
from application.services.ledger import LedgerPoster
from domain.entities import DeviceUnit, StockCount, StockCountLine, StockCountUnit
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    TransactionType,
)
from domain.errors import UnpricedUnitError
from domain.value_objects import Money


class CountPoster:
    def __init__(
        self,
        units: DeviceUnitRepository,
        products: ProductRepository,
        levels: StockLevelRepository,
        pools: CostPoolReader,
        poster: LedgerPoster,
        clock: Clock,
    ) -> None:
        self._units = units
        self._products = products
        self._levels = levels
        self._pools = pools
        self._poster = poster
        self._clock = clock

    async def apply(self, count: StockCount) -> None:
        now = self._clock.now()
        entries: list[PostingEntry] = []

        for unit in count.missing():
            entry = await self._missing_entry(count, unit)
            if entry is not None:
                entries.append(entry)
        for unit in count.unexpected():
            entries.append(await self._unexpected_entry(count, unit, now))
        for line in count.lines:
            entry = await self._line_entry(count, line)
            if entry is not None:
                entries.append(entry)

        await self._poster.post(
            Posting(
                document_type=DocumentType.STOCK_COUNT,
                document_id=count.id,
                entries=entries,
            )
        )

    async def _missing_entry(
        self, count: StockCount, counted: StockCountUnit
    ) -> PostingEntry | None:
        """A handset the snapshot expected and nobody scanned.

        ``None`` where the handset has **already left through a documented
        path** — sold, returned or written off between the count opening and
        confirming. The snapshot froze what the books said hours ago, and a
        phone sold since is not missing, it is sold: the ledger already
        accounts for it, and writing it off again would take its cost out
        twice and leave inventory value negative. The count's report still
        says missing, because that is what the person at the shelf saw.
        """
        # Non-null by ``StockCountUnit.__post_init__``: only a scan can
        # produce a row with no handset behind it, and a missing one was
        # never scanned.
        assert counted.device_unit_id is not None
        unit = await self._units.get(counted.device_unit_id)
        if unit is None:
            raise NotFoundError(
                f"handset {counted.device_unit_id} does not exist in this store"
            )
        if not unit.status.is_on_hand:
            return None
        return PostingEntry(
            movement_type=MovementType.COUNT_ADJUSTMENT,
            product_id=unit.product_id,
            location_id=count.location_id,
            quantity_delta=-1,
            device_unit_id=unit.id,
            new_status=DeviceStatus.WRITTEN_OFF,
            new_location_id=None,
            money=[MoneyEffect(TransactionType.COUNT_ADJUSTMENT, -unit.acquisition_cost)],
            note=f"not found in {count.number}",
        )

    async def _unexpected_entry(
        self, count: StockCount, counted: StockCountUnit, now: datetime
    ) -> PostingEntry:
        """A handset on the shelf that this count did not expect here.

        **Whether it books money depends on whether the store was already
        holding it**, and getting that wrong breaks FR-10.7 in a way nothing
        else would surface:

        - One the books had **on hand somewhere else** is a *location*
          correction. The store owns it, already booked what it paid, and
          its value has not changed — so the goods move and the money does
          not. Booking its cost again would count the same phone twice, and
          ``verify-financials`` would report inventory worth double the
          shelves.
        - One the books had **written off, sold, or never heard of** is
          genuinely entering inventory. On-hand value gains its cost, so the
          money ledger has to gain it too.
        """
        if counted.is_surprise:
            unit = await self._create_surprise(count, counted, now)
            already_held = False
        else:
            unit = await self._known_unit(counted)
            already_held = unit.status.is_on_hand

        return PostingEntry(
            movement_type=MovementType.COUNT_ADJUSTMENT,
            product_id=unit.product_id,
            location_id=count.location_id,
            quantity_delta=1,
            device_unit_id=unit.id,
            new_status=DeviceStatus.IN_STOCK,
            new_location_id=count.location_id,
            money=(
                []
                if already_held
                else [MoneyEffect(TransactionType.COUNT_ADJUSTMENT, unit.acquisition_cost)]
            ),
            note=(
                f"found at this location during {count.number}"
                if already_held
                else f"found on the shelf during {count.number}"
            ),
        )

    async def _known_unit(self, counted: StockCountUnit) -> DeviceUnit:
        """A handset the books already hold a row for, found unexpectedly here.

        It keeps its own cost either way: the store bought it once and the
        count has not changed what it paid.
        """
        assert counted.device_unit_id is not None
        unit = await self._units.get(counted.device_unit_id)
        if unit is None:
            raise NotFoundError(
                f"handset {counted.device_unit_id} does not exist in this store"
            )
        return unit

    async def _create_surprise(
        self, count: StockCount, counted: StockCountUnit, now: datetime
    ) -> DeviceUnit:
        """FR-6.4b: a handset the store had no row for at all.

        It enters ``USED`` and with **no asking price**, so FR-2.14 refuses
        to quote it at the counter until an Owner or Manager prices it. Both
        source columns name this count, which is what the IMEI trace reads
        to say where the handset came from.
        """
        # Both non-null by ``StockCount.confirm()``, which refuses to reach
        # here otherwise and names every offending IMEI at once.
        assert counted.product_id is not None
        assert counted.acquisition_cost is not None

        unit = DeviceUnit(
            imei=counted.imei,
            product_id=counted.product_id,
            status=DeviceStatus.IN_STOCK,
            location_id=count.location_id,
            acquisition_cost=counted.acquisition_cost,
            condition=DeviceCondition.USED,
            source_document_type=DocumentType.STOCK_COUNT,
            source_document_id=count.id,
            created_at=now,
        )
        await self._units.add(unit)
        # No ``DeviceUnitRepricer`` call, unlike ``ReceiptPoster``: there is
        # no intake price to start the markdown log with, and seeding one
        # would be inventing the figure FR-6.4b withholds.
        return unit

    async def _line_entry(
        self, count: StockCount, line: StockCountLine
    ) -> PostingEntry | None:
        """One accessory's adjustment, or None where nothing needs moving.

        **The adjustment is measured against the level as it stands now, not
        against the snapshot.** ``StockCountLine.delta`` is the *report*
        figure — what the counter found against what the books said when the
        count opened, hours ago — and posting it would undo whatever
        happened in between. Three cases sold during the count would be
        booked a second time as a shortage, leaving the level three below a
        shelf that is correct.

        No verifier catches that: the level would be a faithful projection
        of a movement that should never have been written. Which is why the
        live figure is read here rather than trusted from the snapshot.
        """
        if line.counted_quantity is None:
            return None

        level = await self._levels.get_for(line.product_id, count.location_id)
        on_hand = 0 if level is None else level.quantity
        delta = line.counted_quantity - on_hand
        if delta == 0:
            return None

        value = await self._line_value(count, line, delta)
        return PostingEntry(
            movement_type=MovementType.COUNT_ADJUSTMENT,
            product_id=line.product_id,
            location_id=count.location_id,
            quantity_delta=delta,
            money=[MoneyEffect(TransactionType.COUNT_ADJUSTMENT, value)],
            note=f"counted {line.counted_quantity} against {on_hand} on the books",
        )

    async def _line_value(
        self, count: StockCount, line: StockCountLine, delta: int
    ) -> Money:
        """What an accessory adjustment is worth, signed with its delta (§4.6).

        A shortage takes its proportional share out of the pool, exactly as
        a sale would, so a shelf found empty drains to precisely zero.

        A surplus has no purchase document behind it, so it comes on at what
        the pool currently averages — and if the pool is empty there is no
        average and nothing that could stand in for one. That is refused
        rather than booked at zero: a free accessory would dilute the
        average for every later sale, invisibly and forever.
        """
        if delta < 0:
            return -await self._pools.issue_value(
                line.product_id, count.location_id, -delta
            )

        pool = await self._pools.pool_for(line.product_id, count.location_id)
        if pool is None:
            raise NotFoundError(f"product {line.product_id} does not exist in this store")
        unit_cost = pool.average_unit_cost
        if unit_cost is None:
            product = await self._products.get(line.product_id)
            sku = product.sku if product is not None else line.product_id
            raise UnpricedUnitError(
                f"{count.number} found {delta} more {sku} than the books hold, and "
                "this location has never held any — so nothing says what they are "
                "worth. Receive them instead (FR-6.4b)"
            )
        return unit_cost * delta
