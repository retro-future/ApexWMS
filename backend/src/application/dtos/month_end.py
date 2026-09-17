"""The month-end close — FR-10.4 to FR-10.7b, PRD §5.10.

Every figure keeps §4.6's stored sign, which describes cash: purchases,
COGS, write-offs and customer refunds are **negative** because money
left, revenue and supplier return credits positive. Nothing here flips a sign, so ``margin`` is a
plain sum and ``closing`` folds through ``INVENTORY_SIGN`` — the one table
that knows cash signs and inventory signs are not the same.

Debt is a single som figure throughout (§4.7), which is why it is ``Money``
here and ``CurrencyTotals`` everywhere else.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.dtos.discrepancy import Discrepancy
from application.dtos.financing_split import FinancingSplitRow
from application.dtos.inventory_value import LocationInventoryValue
from application.dtos.period import Period
from domain.value_objects import Currency, CurrencyTotals, Money


@dataclass(frozen=True, slots=True)
class AccrualFigures:
    """FR-10.5's accrual view: all sales confirmed in the period, paid or not."""

    opening_inventory: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    purchases: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    cost_of_goods: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    revenue: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    # Negative: money handed back to customers (FR-4.9). Its own line
    # rather than a deduction from revenue, because a month wants both
    # what it sold and what came back.
    sales_returns: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    write_offs: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    supplier_return_credits: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    count_adjustments: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    closing_inventory: CurrencyTotals = field(default_factory=CurrencyTotals.empty)

    @property
    def net_revenue(self) -> CurrencyTotals:
        """Revenue less what came back — refunds are already negative."""
        return self.revenue.merge(self.sales_returns)

    @property
    def margin(self) -> dict[Currency, Money]:
        """Net revenue plus cost, per currency — both are already signed.

        Refunds belong here rather than only on their own line: a return
        nets ``COGS`` down when the goods come back, so a margin over gross
        revenue would count the sale and not its undoing.
        """
        net = self.net_revenue
        return {
            currency: net.of(currency) + self.cost_of_goods.of(currency)
            for currency in net.currencies | self.cost_of_goods.currencies
        }

    @property
    def margin_percent(self) -> dict[Currency, Decimal | None]:
        """Margin over revenue, to one decimal place.

        ``None`` where revenue is zero: a month that sold nothing has no
        margin percentage, and 0.0 would read as one that broke even.
        """
        percentages: dict[Currency, Decimal | None] = {}
        net = self.net_revenue
        for currency, margin in self.margin.items():
            revenue = net.of(currency)
            percentages[currency] = (
                None
                if revenue.amount_minor == 0
                else (
                    Decimal(margin.amount_minor) * 100 / Decimal(revenue.amount_minor)
                ).quantize(Decimal("0.1"))
            )
        return percentages


@dataclass(frozen=True, slots=True)
class SomFigures:
    """Every figure above, read in som (W9 B3).

    A conversion, not a record of what crossed the counter: each dollar
    total was converted at the selling rate in force at the moment it
    happened, and the som totals passed through untouched. It sits beside
    ``AccrualFigures`` rather than inside it, because ``CurrencyTotals``
    structurally cannot hold a mixed sum and that is worth keeping.
    """

    opening_inventory: Money
    purchases: Money
    cost_of_goods: Money
    revenue: Money
    sales_returns: Money
    write_offs: Money
    supplier_return_credits: Money
    count_adjustments: Money
    closing_inventory: Money
    # What the counter really took and paid out, less what the same deals
    # convert to. A sale settled in som at 12 700 while the store quoted
    # 12 500 earned that spread (W9 B7).
    rate_gain: Money
    # The same gap on a store-credit sale, kept apart because it answers a
    # different question: the seller named a som debt above the day's price
    # and that difference is what the shop earns for waiting (W9 B4).
    instalment_income: Money
    basis: ConversionBasis

    @property
    def net_revenue(self) -> Money:
        return self.revenue + self.sales_returns

    @property
    def margin(self) -> Money:
        return self.net_revenue + self.cost_of_goods

    @property
    def profit(self) -> Money:
        """The figure an owner works out on paper: money in less money out."""
        return self.margin + self.rate_gain + self.instalment_income

    @property
    def margin_percent(self) -> Decimal | None:
        """``None`` where nothing was sold; 0.0 would read as breaking even."""
        revenue = self.net_revenue
        if revenue.amount_minor == 0:
            return None
        return (
            Decimal(self.margin.amount_minor) * 100 / Decimal(revenue.amount_minor)
        ).quantize(Decimal("0.1"))


@dataclass(frozen=True, slots=True)
class SettledSale:
    """One sale, as charged and as settled.

    ``received`` is the money the counter really took: the tenders on a sale
    settled there, and on a store-credit sale the som debt agreed instead,
    because a payment against that debt is the same money arriving, not more
    of it. Empty where nothing was recorded, and such a sale is left out
    rather than counted as a total loss.
    """

    at: datetime
    charged: tuple[Money, ...]
    received: tuple[Money, ...]
    # A store-credit sale's gap is the markup the seller named, not a rate
    # they applied: no money crossed the counter to apply one to.
    on_credit: bool = False


@dataclass(frozen=True, slots=True)
class TradeInPayout:
    """One handset bought off a walk-in: what it was valued at, what was paid."""

    at: datetime
    valued: tuple[Money, ...]
    paid: tuple[Money, ...]


@dataclass(frozen=True, slots=True)
class ConversionBasis:
    """What the som column was worked out at, for printing beside it."""

    opening_rate: Decimal
    closing_rate: Decimal
    # True when part of the period predates the first rate ever quoted and
    # took that earliest rate. The report says so rather than implying the
    # store was quoting a rate it had not recorded yet.
    before_the_first_quote: bool


@dataclass(frozen=True, slots=True)
class DebtMovement:
    """FR-10.5's debt/cash view (§4.7). Always som, never a currency pair.

    ``voided`` and ``relieved`` are not among FR-10.5's three lines. They
    are here because cancelling a store-credit sale voids its remaining debt
    (FR-11.11) and a customer return writes some of it off (FR-4.9d), and
    without both lines ``opening + booked - collected`` simply does not
    reach ``closing`` in any month where either happened.
    """

    opening: Money
    booked: Money
    collected: Money
    voided: Money
    relieved: Money
    closing: Money


@dataclass(frozen=True, slots=True)
class MonthEndReport:
    period: Period
    location_id: UUID | None
    figures: AccrualFigures
    # None until the store has quoted a rate at least once.
    som: SomFigures | None
    closing_by_location: list[LocationInventoryValue]
    debt: DebtMovement
    financing: list[FinancingSplitRow]
    discrepancies: list[Discrepancy]

    @property
    def reconciles(self) -> bool:
        """FR-10.7: a mismatch is surfaced beside the figures, not instead
        of them — the owner still gets the month."""
        return not self.discrepancies
