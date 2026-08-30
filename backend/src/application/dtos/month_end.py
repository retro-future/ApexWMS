"""The month-end close — FR-10.4 to FR-10.7b, PRD §5.10.

Every figure keeps §4.6's stored sign, which describes cash: purchases,
COGS and write-offs are **negative** because money left, revenue and
return credits positive. Nothing here flips a sign, so ``margin`` is a
plain sum and ``closing`` folds through ``INVENTORY_SIGN`` — the one table
that knows cash signs and inventory signs are not the same.

Debt is a single som figure throughout (§4.7), which is why it is ``Money``
here and ``CurrencyTotals`` everywhere else.
"""

from dataclasses import dataclass, field
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
    write_offs: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    supplier_return_credits: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    count_adjustments: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    closing_inventory: CurrencyTotals = field(default_factory=CurrencyTotals.empty)

    @property
    def margin(self) -> dict[Currency, Money]:
        """Revenue plus cost, per currency — cost is already negative."""
        return {
            currency: self.revenue.of(currency) + self.cost_of_goods.of(currency)
            for currency in self.revenue.currencies | self.cost_of_goods.currencies
        }

    @property
    def margin_percent(self) -> dict[Currency, Decimal | None]:
        """Margin over revenue, to one decimal place.

        ``None`` where revenue is zero: a month that sold nothing has no
        margin percentage, and 0.0 would read as one that broke even.
        """
        percentages: dict[Currency, Decimal | None] = {}
        for currency, margin in self.margin.items():
            revenue = self.revenue.of(currency)
            percentages[currency] = (
                None
                if revenue.amount_minor == 0
                else (
                    Decimal(margin.amount_minor) * 100 / Decimal(revenue.amount_minor)
                ).quantize(Decimal("0.1"))
            )
        return percentages


@dataclass(frozen=True, slots=True)
class DebtMovement:
    """FR-10.5's debt/cash view (§4.7). Always som, never a currency pair.

    ``voided`` is not one of FR-10.5's three lines. It is here because
    cancelling a store-credit sale voids its remaining debt (FR-11.11), and
    without the line ``opening + booked - collected`` simply does not reach
    ``closing`` in any month where that happened.
    """

    opening: Money
    booked: Money
    collected: Money
    voided: Money
    closing: Money


@dataclass(frozen=True, slots=True)
class MonthEndReport:
    period: Period
    location_id: UUID | None
    figures: AccrualFigures
    closing_by_location: list[LocationInventoryValue]
    debt: DebtMovement
    financing: list[FinancingSplitRow]
    discrepancies: list[Discrepancy]

    @property
    def reconciles(self) -> bool:
        """FR-10.7: a mismatch is surfaced beside the figures, not instead
        of them — the owner still gets the month."""
        return not self.discrepancies
