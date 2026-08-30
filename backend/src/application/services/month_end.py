"""The period close — FR-10.4 to FR-10.7b, PRD §5.10.

Opening and closing inventory are both rolled forward from the money ledger
since inception, which is what makes "opening = previous closing" exact
rather than approximately true (§5.10). The goods side is computed
separately by ``InventoryValuer`` and compared against the closing figure;
a mismatch is reported beside the numbers, never folded into them.

The debt and cash block is store-wide even when the report is scoped to one
location. Debt belongs to a customer, not a shelf, and a payment records no
location at all — a per-location debt figure would be a fiction.
"""

from uuid import UUID

from application.dtos import (
    AccrualFigures,
    DebtMovement,
    Discrepancy,
    LocationInventoryValue,
    MonthEndReport,
    Period,
)
from application.ports import FinancialTransactionQueries, MonthEndQueries
from application.services.cost_pools import inventory_effect
from application.services.inventory_value import InventoryValuer
from application.services.period import PeriodResolver
from application.services.verification.balances import BalanceVerifier
from domain.enums import TransactionType
from domain.value_objects import Currency, CurrencyTotals, Money


class MonthEndReporter:
    def __init__(
        self,
        periods: PeriodResolver,
        transactions: FinancialTransactionQueries,
        debts: MonthEndQueries,
        inventory: InventoryValuer,
        balances: BalanceVerifier,
    ) -> None:
        self._periods = periods
        self._transactions = transactions
        self._debts = debts
        self._inventory = inventory
        self._balances = balances

    async def report(
        self, year: int, month: int, location_id: UUID | None = None
    ) -> MonthEndReport:
        period = await self._periods.month(year, month)
        figures = await self._figures(period, location_id)
        by_location = await self._inventory.by_location(period.end, location_id)
        debt = await self._debt(period)
        return MonthEndReport(
            period=period,
            location_id=location_id,
            figures=figures,
            closing_by_location=by_location,
            debt=debt,
            financing=await self._debts.sales_by_financing(
                period.start, period.end, location_id
            ),
            discrepancies=[
                *self._inventory_discrepancies(figures, by_location),
                *self._debt_discrepancies(debt),
                *await self._balances.verify(),
            ],
        )

    async def _figures(self, period: Period, location_id: UUID | None) -> AccrualFigures:
        opening = inventory_effect(
            await self._transactions.totals_by_type(
                until=period.start, location_id=location_id
            )
        )
        moved = await self._transactions.totals_by_type(
            since=period.start, until=period.end, location_id=location_id
        )
        per_type: dict[TransactionType, CurrencyTotals] = {}
        for (txn_type, _), amount in moved.items():
            per_type[txn_type] = per_type.get(txn_type, CurrencyTotals.empty()).add(amount)

        def category(txn_type: TransactionType) -> CurrencyTotals:
            return per_type.get(txn_type, CurrencyTotals.empty())

        return AccrualFigures(
            opening_inventory=opening,
            purchases=category(TransactionType.PURCHASE),
            cost_of_goods=category(TransactionType.COGS),
            revenue=category(TransactionType.SALE_REVENUE),
            write_offs=category(TransactionType.WRITE_OFF_LOSS),
            supplier_return_credits=category(TransactionType.SUPPLIER_RETURN_CREDIT),
            count_adjustments=category(TransactionType.COUNT_ADJUSTMENT),
            closing_inventory=opening.merge(inventory_effect(moved)),
        )

    async def _debt(self, period: Period) -> DebtMovement:
        """Store-wide (see the module docstring), and always som (§4.7)."""
        collected = (
            await self._transactions.totals_by_type(since=period.start, until=period.end)
        ).get(
            (TransactionType.PAYMENT_RECEIVED, Currency.UZS), Money.zero(Currency.UZS)
        )
        return DebtMovement(
            opening=await self._debts.debt_at(period.start),
            booked=await self._debts.debt_booked_between(period.start, period.end),
            collected=collected,
            voided=await self._debts.debt_voided_between(period.start, period.end),
            closing=await self._debts.debt_at(period.end),
        )

    @staticmethod
    def _inventory_discrepancies(
        figures: AccrualFigures, by_location: list[LocationInventoryValue]
    ) -> list[Discrepancy]:
        """FR-10.7: the money ledger's closing figure against what the goods
        say, per currency. Never summed across the two."""
        on_hand = CurrencyTotals.empty()
        for entry in by_location:
            on_hand = on_hand.merge(entry.value)

        found: list[Discrepancy] = []
        for currency in sorted(
            figures.closing_inventory.currencies | on_hand.currencies,
            key=lambda one: one.value,
        ):
            books = figures.closing_inventory.of(currency)
            stock = on_hand.of(currency)
            if books != stock:
                found.append(
                    Discrepancy(
                        subject=f"closing inventory value in {currency.value}",
                        expected=books.format(),
                        found=stock.format(),
                    )
                )
        return found

    @staticmethod
    def _debt_discrepancies(debt: DebtMovement) -> list[Discrepancy]:
        """FR-10.7b: the movement has to land on the closing balance."""
        rolled = debt.opening + debt.booked - debt.collected - debt.voided
        if rolled == debt.closing:
            return []
        return [
            Discrepancy(
                subject="closing customer debt",
                expected=rolled.format(),
                found=debt.closing.format(),
            )
        ]
