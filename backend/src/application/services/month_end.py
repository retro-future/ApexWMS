"""The period close — FR-10.4 to FR-10.7b, PRD §5.10.

Opening and closing inventory are both rolled forward from the money ledger
since inception, which is what makes "opening = previous closing" exact
rather than approximately true (§5.10). The goods side is computed
separately by ``InventoryValuer`` and compared against the closing figure;
a mismatch is reported beside the numbers, never folded into them.

The debt and cash block is store-wide even when the report is scoped to one
location. Debt belongs to a customer, not a shelf, and a payment records no
location at all — a per-location debt figure would be a fiction.

Beside the per-currency figures sits one more set read in som (W9 B3),
each figure converted at the rate in force when it happened, and two lines that are
not conversions at all: the gap between the money that really crossed the
counter and what the same deals convert to, split into the rate the counter
traded at and the markup a store-credit sale carries. Adding both to the
converted margin gives the figure an owner works out on paper. The
per-currency figures stay exactly what they were, down to the last minor
unit.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository
from application.dtos import (
    AccrualFigures,
    ConversionBasis,
    DebtMovement,
    Discrepancy,
    LocationInventoryValue,
    MonthEndReport,
    Period,
    SomFigures,
)
from application.ports import FinancialTransactionQueries, MonthEndQueries
from application.services.cost_pools import inventory_effect
from application.services.inventory_value import InventoryValuer
from application.services.period import PeriodResolver
from application.services.som_conversion import SomConverter
from application.services.verification.balances import BalanceVerifier
from application.specs import RateHistory
from domain.entities import ExchangeRate
from domain.enums import RateKind, TransactionType
from domain.value_objects import Currency, CurrencyTotals, Money
from infrastructure.persistence.tenant.models import ExchangeRateModel

_RateTotals = dict[tuple[TransactionType, Currency, datetime | None], Money]


@dataclass(frozen=True, slots=True)
class _Earned:
    """The two gaps between real money and the converted figures."""

    on_the_rate: Money
    on_credit: Money


class MonthEndReporter:
    def __init__(
        self,
        periods: PeriodResolver,
        transactions: FinancialTransactionQueries,
        debts: MonthEndQueries,
        inventory: InventoryValuer,
        balances: BalanceVerifier,
        rates: TenantAppendOnlyRepository[ExchangeRate, ExchangeRateModel],
    ) -> None:
        self._periods = periods
        self._transactions = transactions
        self._debts = debts
        self._inventory = inventory
        self._balances = balances
        self._rates = rates

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
            som=await self._som(period, location_id),
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
            sales_returns=category(TransactionType.SALES_RETURN_REFUND),
            write_offs=category(TransactionType.WRITE_OFF_LOSS),
            supplier_return_credits=category(TransactionType.SUPPLIER_RETURN_CREDIT),
            count_adjustments=category(TransactionType.COUNT_ADJUSTMENT),
            closing_inventory=opening.merge(inventory_effect(moved)),
        )

    async def _som(self, period: Period, location_id: UUID | None) -> SomFigures | None:
        """The same month read in som, each figure at the rate of its moment.

        The *selling* rate throughout: it is what the store quotes the
        customer, so it is the one figure a dollar price was ever meant to
        be read at.
        """
        converter = SomConverter(
            await self._rates.find(RateHistory(RateKind.SALE)), period.timezone
        )
        if converter.is_empty:
            return None

        before = await self._transactions.totals_by_type_and_rate(
            rate_changes=converter.rate_changes,
            until=period.start,
            location_id=location_id,
        )
        during = await self._transactions.totals_by_type_and_rate(
            rate_changes=converter.rate_changes,
            since=period.start,
            until=period.end,
            location_id=location_id,
        )
        opening = self._in_som(before, converter)
        moved = self._in_som(during, converter)

        def category(txn_type: TransactionType) -> Money:
            return moved.get((txn_type, Currency.UZS), Money.zero(Currency.UZS))

        earned = await self._earned_beyond_the_rate(period, location_id, converter)
        opening_value = inventory_effect(opening).of(Currency.UZS)
        return SomFigures(
            opening_inventory=opening_value,
            purchases=category(TransactionType.PURCHASE),
            cost_of_goods=category(TransactionType.COGS),
            revenue=category(TransactionType.SALE_REVENUE),
            sales_returns=category(TransactionType.SALES_RETURN_REFUND),
            write_offs=category(TransactionType.WRITE_OFF_LOSS),
            supplier_return_credits=category(TransactionType.SUPPLIER_RETURN_CREDIT),
            count_adjustments=category(TransactionType.COUNT_ADJUSTMENT),
            closing_inventory=opening_value
            + inventory_effect(moved).of(Currency.UZS),
            rate_gain=earned.on_the_rate,
            instalment_income=earned.on_credit,
            basis=ConversionBasis(
                opening_rate=converter.on(period.start),
                closing_rate=converter.on(period.end - timedelta(microseconds=1)),
                before_the_first_quote=any(
                    converter.before_the_first_quote(at)
                    for _, _, at in (*before, *during)
                ),
            ),
        )

    async def _earned_beyond_the_rate(
        self, period: Period, location_id: UUID | None, converter: SomConverter
    ) -> _Earned:
        """Real money in and out, less what the same deals convert to.

        Two figures, not one. A sale settled at the counter is money the
        seller took at their own rate, and the gap is a rate gain. A
        store-credit sale is a som debt the seller named out of the air, so
        the gap is the shop's markup for waiting. A sale nobody recorded a
        settlement for is skipped: an unknown figure is not a loss.
        """
        on_the_rate = Money.zero(Currency.UZS)
        on_credit = Money.zero(Currency.UZS)
        for sale in await self._debts.settled_sales(
            since=period.start,
            until=period.end,
            location_id=location_id,
        ):
            if not sale.received:
                continue
            gap = self._som_of(sale.received, sale.at, converter) - self._som_of(
                sale.charged, sale.at, converter
            )
            if sale.on_credit:
                on_credit += gap
            else:
                on_the_rate += gap
        for bought in await self._debts.trade_in_payouts(
            since=period.start,
            until=period.end,
            location_id=location_id,
        ):
            if not bought.paid:
                continue
            on_the_rate += self._som_of(
                bought.valued, bought.at, converter
            ) - self._som_of(bought.paid, bought.at, converter)
        return _Earned(on_the_rate=on_the_rate, on_credit=on_credit)

    @staticmethod
    def _som_of(
        amounts: tuple[Money, ...], at: datetime, converter: SomConverter
    ) -> Money:
        total = Money.zero(Currency.UZS)
        for amount in amounts:
            total += converter.convert(amount, at)
        return total

    @staticmethod
    def _in_som(
        totals: _RateTotals, converter: SomConverter
    ) -> dict[tuple[TransactionType, Currency], Money]:
        """Collapse the split by rate back to one som figure per category."""
        running: dict[tuple[TransactionType, Currency], Money] = {}
        for (txn_type, _, at), amount in totals.items():
            key = (txn_type, Currency.UZS)
            in_som = converter.convert(amount, at)
            running[key] = running.get(key, Money.zero(Currency.UZS)) + in_som
        return running

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
            relieved=await self._debts.debt_relieved_between(
                period.start, period.end
            ),
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
        rolled = (
            debt.opening + debt.booked - debt.collected - debt.voided - debt.relieved
        )
        if rolled == debt.closing:
            return []
        return [
            Discrepancy(
                subject="closing customer debt",
                expected=rolled.format(),
                found=debt.closing.format(),
            )
        ]
