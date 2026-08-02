"""Auditing what the ledgers imply against what the projections say.

*"The ledger is the source of truth; projections are always rebuildable"*
(PRD §11) is only worth anything if something actually rebuilds them. This
is that something — the service behind ``apexwms verify-projections`` and
``apexwms verify-financials``.

Two checks, deliberately separate because they can fail for different
reasons:

- **``ProjectionVerifier``** recomputes stock levels, device statuses and
  both price projections from their append-only sources (§4.3, §4.5b). A
  mismatch means something wrote a projection without writing the row
  behind it.
- **``LedgerReconciler``** is FR-10.7's money-side analogue: on-hand
  inventory value recomputed from stock, **checked per currency** against
  what the financial ledger says the store should be holding. A mismatch
  means goods and money disagree, which the month-end report surfaces as
  an error and never silently reconciles.

Everything here is driven by ports, so both are testable with fakes and no
database — which matters, because a verification routine that can only be
exercised against production is one nobody trusts.
"""

from dataclasses import dataclass
from uuid import UUID

from application.ports import (
    DeviceUnitPriceChangeRepository,
    DeviceUnitRepository,
    FinancialTransactionRepository,
    ProductPriceChangeRepository,
    ProductRepository,
    StockLevelRepository,
    StockMovementRepository,
)
from domain.entities import DeviceUnit
from domain.enums import TransactionType
from domain.services import CostPool, project_unit_state
from domain.value_objects import Currency, Money

# How many catalog rows a sweep pulls at a time.
_PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class Discrepancy:
    """One thing that does not add up, in terms an operator can act on."""

    subject: str
    expected: str
    found: str

    def __str__(self) -> str:
        return f"{self.subject}: ledger says {self.expected}, projection says {self.found}"


class ProjectionVerifier:
    """Rebuilds every projection from its source and reports the gaps."""

    def __init__(
        self,
        movements: StockMovementRepository,
        levels: StockLevelRepository,
        units: DeviceUnitRepository,
        unit_prices: DeviceUnitPriceChangeRepository,
        products: ProductRepository,
        product_prices: ProductPriceChangeRepository,
    ) -> None:
        self._movements = movements
        self._levels = levels
        self._units = units
        self._unit_prices = unit_prices
        self._products = products
        self._product_prices = product_prices

    async def verify(self) -> list[Discrepancy]:
        return [
            *await self._verify_levels(),
            *await self._verify_units(),
            *await self._verify_unit_prices(),
            *await self._verify_catalog_prices(),
        ]

    async def _verify_levels(self) -> list[Discrepancy]:
        """Every (product, location) the ledger has touched, plus every
        level that exists.

        Driven from **both** ends on purpose: sweeping only the levels
        would miss a movement whose level was never written at all, and
        sweeping only the ledger would miss a level invented out of thin
        air. Each is a different bug and both are worth catching.
        """
        pairs = set(await self._movements.list_moved_pairs())
        stored = {
            (level.product_id, level.location_id): level
            for level in await self._levels.list_all()
        }
        found: list[Discrepancy] = []

        for pair in pairs | set(stored):
            product_id, location_id = pair
            expected = await self._movements.net_quantity(product_id, location_id)
            level = stored.get(pair)
            actual = 0 if level is None else level.quantity
            if expected != actual:
                found.append(
                    Discrepancy(
                        subject=f"stock level product={product_id} location={location_id}",
                        expected=str(expected),
                        found="no row" if level is None else str(actual),
                    )
                )
        return found

    async def _units_to_sweep(self) -> list[DeviceUnit]:
        """Every handset either side thinks is in stock.

        Driven from **both** ends, like the level sweep and for the same
        reason. A unit the projection has silently marked ``SOLD`` is
        invisible from the projection side — and is the drift most worth
        catching, because the phone is still on the shelf. A store's whole
        sales history is still not replayed: units that both sides agree
        have left are skipped.
        """
        by_id = {unit.id: unit for unit in await self._units.list_on_hand()}
        for unit_id in await self._movements.list_units_on_hand():
            if unit_id not in by_id:
                unit = await self._units.get(unit_id)
                if unit is not None:
                    by_id[unit_id] = unit
        return list(by_id.values())

    async def _verify_units(self) -> list[Discrepancy]:
        """Each handset's status and location against its own timeline."""
        found: list[Discrepancy] = []
        for unit in await self._units_to_sweep():
            history = await self._movements.list_for_unit(unit.id)
            if not history:
                found.append(
                    Discrepancy(
                        subject=f"device unit {unit.imei}",
                        expected="no movements at all",
                        found=f"{unit.status.value} at {unit.location_id}",
                    )
                )
                continue
            status, location_id = project_unit_state(history)
            if (status, location_id) != (unit.status, unit.location_id):
                found.append(
                    Discrepancy(
                        subject=f"device unit {unit.imei}",
                        expected=f"{status.value} at {location_id}",
                        found=f"{unit.status.value} at {unit.location_id}",
                    )
                )
        return found

    async def _verify_unit_prices(self) -> list[Discrepancy]:
        """``asking_price`` against the last row of the unit's price log."""
        found: list[Discrepancy] = []
        for unit in await self._units_to_sweep():
            latest = await self._unit_prices.latest_for_unit(unit.id)
            expected = latest.new_price if latest else None
            if expected != unit.asking_price:
                found.append(
                    Discrepancy(
                        subject=f"asking price of {unit.imei}",
                        expected=_show(expected),
                        found=_show(unit.asking_price),
                    )
                )
        return found

    async def _verify_catalog_prices(self) -> list[Discrepancy]:
        """``default_sale_price`` against the last row of the catalog log.

        Paged rather than fetched whole: a catalog is the one table here
        that a large store could plausibly have tens of thousands of rows
        in, and a sweep that only works on small tenants is not a sweep.
        """
        found: list[Discrepancy] = []
        page = 1
        while True:
            products, total = await self._products.list_page(page, _PAGE_SIZE)
            for product in products:
                latest = await self._product_prices.latest_for_product(product.id)
                expected = latest.new_price if latest else None
                if expected != product.default_sale_price:
                    found.append(
                        Discrepancy(
                            subject=f"catalog price of {product.sku}",
                            expected=_show(expected),
                            found=_show(product.default_sale_price),
                        )
                    )
            if page * _PAGE_SIZE >= total:
                return found
            page += 1


class LedgerReconciler:
    """FR-10.7: goods and money must agree, per currency."""

    def __init__(
        self,
        units: DeviceUnitRepository,
        transactions: FinancialTransactionRepository,
        movements: StockMovementRepository,
        products: ProductRepository,
    ) -> None:
        self._units = units
        self._transactions = transactions
        self._movements = movements
        self._products = products

    async def on_hand_value(self) -> dict[Currency, Money]:
        """What the store is holding, **per currency**, computed from stock.

        Two rules, because the two tracking types genuinely differ (§4.6):
        serialized phones by specific identification — each unit's own
        cost, a fact rather than a model — and quantity accessories by a
        weighted-average pool replayed from the ledger.

        This is the *independent* side of FR-10.7. The quantities come from
        the stock ledger and the purchase costs from the money ledger, so a
        COGS booked at the wrong average shows up here as a disagreement
        with what the money ledger thinks it is holding.
        """
        totals: dict[Currency, Money] = {}
        for unit in await self._units.list_on_hand():
            _accumulate(totals, unit.acquisition_cost)
        for product_id, location_id in await self._movements.list_moved_pairs():
            pool = await self._replay_pool(product_id, location_id)
            if pool is not None and not pool.value.is_zero:
                _accumulate(totals, pool.value)
        return totals

    async def _replay_pool(self, product_id: UUID, location_id: UUID) -> CostPool | None:
        """Rebuild one accessory's cost pool from the two ledgers.

        Receipts take their value from the ``PURCHASE`` (or surplus
        ``COUNT_ADJUSTMENT``) entry the same document wrote, in **total**
        rather than per unit — dividing a line's cost out and multiplying
        it back would introduce a rounding error that was never in the
        data. Issues take their proportional share of the pool
        (``CostPool.issue``), which is what makes a sold-out pool land on
        exactly zero.
        """
        product = await self._products.get(product_id)
        if product is None:
            return None

        value_in = await self._value_added_per_document(product_id, location_id)
        pool = CostPool.empty(product.currency)
        for movement in await self._movements.list_for_pair(product_id, location_id):
            if movement.quantity_delta > 0:
                pool = pool.receive_total(
                    movement.quantity_delta,
                    value_in.pop(movement.document_id, Money.zero(product.currency)),
                )
            else:
                pool, _ = pool.issue(-movement.quantity_delta)
        return pool

    async def _value_added_per_document(
        self, product_id: UUID, location_id: UUID
    ) -> dict[UUID, Money]:
        """How much each document added to this pool's value.

        Only the inbound categories: an issue's cost is *computed* from the
        pool, never read back out of the ledger, or the check would be
        comparing the money ledger against itself.
        """
        added: dict[UUID, Money] = {}
        for txn in await self._transactions.list_for_pair(product_id, location_id):
            sign = _INVENTORY_SIGN.get(txn.txn_type)
            if sign is None:
                continue
            contribution = txn.amount * sign
            if contribution.is_negative or contribution.is_zero:
                continue
            running = added.get(txn.document_id)
            added[txn.document_id] = (
                contribution if running is None else running + contribution
            )
        return added

    async def ledger_value(self) -> dict[Currency, Money]:
        """What the money ledger says the store should be holding.

        ``purchases − COGS − write-offs − return credits ± adjustments``
        (FR-10.5), computed since inception because the ledger is complete
        and immutable — no stored snapshot is needed for correctness
        (§5.10).

        Revenue is deliberately absent: it is what the goods *sold for*,
        not what they *cost*, and adding it here would compare a selling
        price against an inventory value.
        """
        totals: dict[Currency, Money] = {}
        for (txn_type, _), amount in (await self._transactions.totals_by_type()).items():
            sign = _INVENTORY_SIGN.get(txn_type)
            if sign is not None:
                _accumulate(totals, amount * sign)
        return totals

    async def reconcile(self) -> list[Discrepancy]:
        """A mismatch is surfaced, never silently corrected (FR-10.7)."""
        on_hand = await self.on_hand_value()
        ledger = await self.ledger_value()
        found: list[Discrepancy] = []

        for currency in sorted(set(on_hand) | set(ledger), key=lambda c: c.value):
            stock = on_hand.get(currency, Money.zero(currency))
            books = ledger.get(currency, Money.zero(currency))
            if stock != books:
                found.append(
                    Discrepancy(
                        subject=f"inventory value in {currency.value}",
                        expected=books.format(),
                        found=stock.format(),
                    )
                )
        return found


# How each category moves *inventory value*, which is not the same as how
# it moves money — and the mismatch is the trap this table exists to close.
#
# §4.6's signs describe cash: a ``PURCHASE`` is stored negative because
# money left the till, while the goods it bought made the shelves *worth
# more*. A ``SUPPLIER_RETURN_CREDIT`` is stored positive for the same
# reason in reverse. So two categories have to be flipped to read as
# inventory, and ``COUNT_ADJUSTMENT`` — whose sign already describes goods
# found or missing — does not.
#
# Getting this wrong does not crash anything. It produces a reconciliation
# that is off by exactly twice the purchases, which is the sort of figure
# somebody spends a day chasing.
_INVENTORY_SIGN: dict[TransactionType, int] = {
    TransactionType.PURCHASE: -1,
    TransactionType.COGS: +1,
    TransactionType.WRITE_OFF_LOSS: +1,
    TransactionType.SUPPLIER_RETURN_CREDIT: -1,
    TransactionType.COUNT_ADJUSTMENT: +1,
}
# SALE_REVENUE and PAYMENT_RECEIVED are absent, not zero: they are figures
# about the customer, and no sign would make them belong here.


def _accumulate(totals: dict[Currency, Money], amount: Money) -> None:
    """Add *amount* to its own currency's running total, and only its own.

    The one operation every per-currency figure in this file is built from
    — so there is nowhere a USD amount could land in the UZS column
    (§4.5 rule 4).
    """
    running = totals.get(amount.currency)
    totals[amount.currency] = amount if running is None else running + amount


def _show(amount: Money | None) -> str:
    return "unpriced" if amount is None else amount.format()
