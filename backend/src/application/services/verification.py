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
- **``BalanceVerifier``** is the debt side (§4.7, FR-10.7b). Customer
  balances are *always* derived, so there is no cached projection to check
  them against — what it audits instead is that the two independent records
  of the same fact agree: the ``payments`` table and the money ledger's
  ``PAYMENT_RECEIVED`` rows.

Everything here is driven by ports, so all three are testable with fakes and
no database — which matters, because a verification routine that can only be
exercised against production is one nobody trusts.
"""

from dataclasses import dataclass
from uuid import UUID

from application.ports import (
    DeviceUnitPriceChangeRepository,
    DeviceUnitRepository,
    FinancialTransactionRepository,
    PaymentRepository,
    ProductPriceChangeRepository,
    ProductRepository,
    SalesInvoiceRepository,
    StockLevelRepository,
    StockMovementRepository,
)
from application.services.cost_pools import INVENTORY_SIGN, CostPoolReader
from domain.entities import DeviceUnit, Payment
from domain.enums import TransactionType
from domain.services import UnitProjector
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
        projector: UnitProjector,
    ) -> None:
        self._movements = movements
        self._levels = levels
        self._units = units
        self._unit_prices = unit_prices
        self._products = products
        self._product_prices = product_prices
        self._projector = projector

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
            status, location_id = self._projector.project(history)
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
        pools: CostPoolReader,
    ) -> None:
        self._units = units
        self._transactions = transactions
        self._movements = movements
        self._pools = pools

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
            pool = await self._pools.pool_for(product_id, location_id)
            if pool is not None and not pool.value.is_zero:
                _accumulate(totals, pool.value)
        return totals

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
            sign = INVENTORY_SIGN.get(txn_type)
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


class BalanceVerifier:
    """§4.7: every customer balance recomputed from the rows behind it."""

    def __init__(
        self,
        invoices: SalesInvoiceRepository,
        payments: PaymentRepository,
        transactions: FinancialTransactionRepository,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._transactions = transactions

    async def verify(self) -> list[Discrepancy]:
        """A mismatch is reported, never repaired.

        Rewriting a debt to match the payments would destroy the evidence
        of whatever wrote it wrong — and this is the one sweep whose
        findings are somebody's money.
        """
        payments = await self._payments.list_all()
        return [
            *await self._verify_invoices(payments),
            *await self._verify_ledger_agrees(payments),
        ]

    async def _verify_invoices(self, payments: list[Payment]) -> list[Discrepancy]:
        """Each invoice's terms against what has been collected on it.

        Two different bugs, both worth catching: a store-credit sale paid
        past its debt (the balance has gone negative), and a settled sale
        carrying a debt or a payment at all — FR-11.4's "creates no debt
        anywhere" as a sweep rather than a single test.
        """
        collected: dict[UUID, Money] = {}
        for payment in payments:
            _accumulate_for(collected, payment.sales_invoice_id, payment.amount)

        found: list[Discrepancy] = []
        for invoice_id, paid in collected.items():
            invoice = await self._invoices.get(invoice_id)
            if invoice is None:
                found.append(
                    Discrepancy(
                        subject=f"payments against invoice {invoice_id}",
                        expected="an invoice to settle",
                        found=f"{paid.format()} collected against no invoice",
                    )
                )
                continue
            if not invoice.payment_type.opens_debt or invoice.debt is None:
                found.append(
                    Discrepancy(
                        subject=f"payments against {invoice.number}",
                        expected=f"none — it is {invoice.payment_type.value}",
                        found=paid.format(),
                    )
                )
                continue
            if paid > invoice.debt:
                found.append(
                    Discrepancy(
                        subject=f"debt on {invoice.number}",
                        expected=f"at least the {paid.format()} collected",
                        found=invoice.debt.format(),
                    )
                )
        return found

    async def _verify_ledger_agrees(self, payments: list[Payment]) -> list[Discrepancy]:
        """The ``payments`` table against the money ledger.

        Both are written in one transaction by ``PaymentPoster``, so they
        can only disagree if something wrote one without the other — which
        is precisely the bug a sweep exists to find.
        """
        recorded = Money.zero(Currency.UZS)
        for payment in payments:
            recorded = recorded + payment.amount

        totals = await self._transactions.totals_by_type()
        booked = totals.get(
            (TransactionType.PAYMENT_RECEIVED, Currency.UZS), Money.zero(Currency.UZS)
        )
        if recorded == booked:
            return []
        return [
            Discrepancy(
                subject="cash collected on store credit",
                expected=booked.format(),
                found=recorded.format(),
            )
        ]


def _accumulate_for(totals: dict[UUID, Money], key: UUID, amount: Money) -> None:
    running = totals.get(key)
    totals[key] = amount if running is None else running + amount


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
