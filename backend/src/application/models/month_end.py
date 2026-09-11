"""The month-end close on the wire — FR-10.4 to FR-10.9, PRD §5.10.

Every money figure is a list of per-currency subtotals, never a number, so
there is nowhere a USD total and a UZS total could be added together
(FR-2.11). Debt is the one exception: it is a single som amount by
definition (§4.7), not a pair.

Signs are §4.6's, unchanged: ``purchases``, ``costOfGoods`` and
``writeOffs`` are negative because money left. Nothing here flips one —
the screen and the PDF re-sign for a stock-value view (see
``docs/architecture/ledgers.md``), but the payload does not.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import (
    AccrualFigures,
    DebtMovement,
    Discrepancy,
    FinancingSplitRow,
    LocationInventoryValue,
    MonthEndReport,
    Period,
    SomFigures,
)
from application.models.exchange_rate import ExchangeRateData
from application.models.money import MoneyData
from domain.enums import PaymentType
from domain.value_objects import Currency


class PeriodData(CamelModel):
    year: int
    month: int
    timezone: str
    start: datetime
    end: datetime

    @classmethod
    def from_entity(cls, period: Period) -> PeriodData:
        return cls(
            year=period.year,
            month=period.month,
            timezone=period.timezone,
            start=period.start,
            end=period.end,
        )


class MarginPercentData(CamelModel):
    """Margin over revenue, per currency. ``percent`` is null where the
    period sold nothing — 0.0 would read as breaking even."""

    currency: Currency
    percent: Decimal | None

    @classmethod
    def from_entity(cls, figures: AccrualFigures) -> list[MarginPercentData]:
        return [
            cls(currency=currency, percent=percent)
            for currency, percent in sorted(
                figures.margin_percent.items(), key=lambda pair: pair[0].value
            )
        ]


class AccrualFiguresData(CamelModel):
    opening_inventory: list[MoneyData]
    purchases: list[MoneyData]
    cost_of_goods: list[MoneyData]
    revenue: list[MoneyData]
    # Negative: money handed back to customers (FR-4.9).
    sales_returns: list[MoneyData]
    write_offs: list[MoneyData]
    supplier_return_credits: list[MoneyData]
    count_adjustments: list[MoneyData]
    closing_inventory: list[MoneyData]
    margin: list[MoneyData]
    margin_percent: list[MarginPercentData]

    @classmethod
    def from_entity(cls, figures: AccrualFigures) -> AccrualFiguresData:
        return cls(
            opening_inventory=MoneyData.from_entity(
                figures.opening_inventory.as_dict()
            ),
            purchases=MoneyData.from_entity(figures.purchases.as_dict()),
            cost_of_goods=MoneyData.from_entity(
                figures.cost_of_goods.as_dict()
            ),
            revenue=MoneyData.from_entity(figures.revenue.as_dict()),
            sales_returns=MoneyData.from_entity(
                figures.sales_returns.as_dict()
            ),
            write_offs=MoneyData.from_entity(figures.write_offs.as_dict()),
            supplier_return_credits=MoneyData.from_entity(
                figures.supplier_return_credits.as_dict()
            ),
            count_adjustments=MoneyData.from_entity(
                figures.count_adjustments.as_dict()
            ),
            closing_inventory=MoneyData.from_entity(
                figures.closing_inventory.as_dict()
            ),
            margin=MoneyData.from_entity(figures.margin),
            margin_percent=MarginPercentData.from_entity(figures),
        )


class LocationInventoryValueData(CamelModel):
    location_id: UUID
    location_name: str | None
    quantity: int
    value: list[MoneyData]

    @classmethod
    def from_entity(cls, entry: LocationInventoryValue) -> LocationInventoryValueData:
        return cls(
            location_id=entry.location_id,
            location_name=entry.location_name,
            quantity=entry.quantity,
            value=MoneyData.from_entity(entry.value.as_dict()),
        )


class DebtMovementData(CamelModel):
    """Always som, and always store-wide — debt belongs to a customer, not
    a shelf, so a location-scoped report does not narrow it."""

    opening: MoneyData
    booked: MoneyData
    collected: MoneyData
    voided: MoneyData
    # Debt written off by confirmed customer returns (FR-4.9d).
    relieved: MoneyData
    closing: MoneyData

    @classmethod
    def from_entity(cls, debt: DebtMovement) -> DebtMovementData:
        return cls(
            opening=MoneyData.from_entity(debt.opening),
            booked=MoneyData.from_entity(debt.booked),
            collected=MoneyData.from_entity(debt.collected),
            voided=MoneyData.from_entity(debt.voided),
            relieved=MoneyData.from_entity(debt.relieved),
            closing=MoneyData.from_entity(debt.closing),
        )


class FinancingSplitData(CamelModel):
    payment_type: PaymentType
    credit_company_id: UUID | None
    credit_company_name: str | None
    invoice_count: int
    revenue: list[MoneyData]

    @classmethod
    def from_entity(cls, row: FinancingSplitRow) -> FinancingSplitData:
        return cls(
            payment_type=row.payment_type,
            credit_company_id=row.credit_company_id,
            credit_company_name=row.credit_company_name,
            invoice_count=row.invoice_count,
            revenue=MoneyData.from_entity({row.revenue.currency: row.revenue}),
        )


class DiscrepancyData(CamelModel):
    subject: str
    expected: str
    found: str

    @classmethod
    def from_entity(cls, found: Discrepancy) -> DiscrepancyData:
        return cls(subject=found.subject, expected=found.expected, found=found.found)


class SomFiguresData(CamelModel):
    """The same month read in som (W9 B3).

    A conversion, not what crossed the counter, so ``basis`` travels with
    it and the screen prints both together.
    """

    opening_inventory: MoneyData
    purchases: MoneyData
    cost_of_goods: MoneyData
    revenue: MoneyData
    sales_returns: MoneyData
    write_offs: MoneyData
    supplier_return_credits: MoneyData
    count_adjustments: MoneyData
    closing_inventory: MoneyData
    margin: MoneyData
    margin_percent: Decimal | None
    # Not a conversion: the money that really crossed the counter, less
    # what the same deals convert to.
    rate_gain: MoneyData
    instalment_income: MoneyData
    profit: MoneyData
    opening_rate: str
    closing_rate: str
    # True when part of the period predates the first rate ever quoted.
    before_the_first_quote: bool

    @classmethod
    def from_entity(cls, figures: SomFigures) -> SomFiguresData:
        return cls(
            opening_inventory=MoneyData.from_entity(figures.opening_inventory),
            purchases=MoneyData.from_entity(figures.purchases),
            cost_of_goods=MoneyData.from_entity(figures.cost_of_goods),
            revenue=MoneyData.from_entity(figures.revenue),
            sales_returns=MoneyData.from_entity(figures.sales_returns),
            write_offs=MoneyData.from_entity(figures.write_offs),
            supplier_return_credits=MoneyData.from_entity(
                figures.supplier_return_credits
            ),
            count_adjustments=MoneyData.from_entity(figures.count_adjustments),
            closing_inventory=MoneyData.from_entity(figures.closing_inventory),
            margin=MoneyData.from_entity(figures.margin),
            margin_percent=figures.margin_percent,
            rate_gain=MoneyData.from_entity(figures.rate_gain),
            instalment_income=MoneyData.from_entity(figures.instalment_income),
            profit=MoneyData.from_entity(figures.profit),
            opening_rate=ExchangeRateData.plain(figures.basis.opening_rate),
            closing_rate=ExchangeRateData.plain(figures.basis.closing_rate),
            before_the_first_quote=figures.basis.before_the_first_quote,
        )


class MonthEndReportData(CamelModel):
    period: PeriodData
    location_id: UUID | None
    figures: AccrualFiguresData
    som: SomFiguresData | None
    closing_by_location: list[LocationInventoryValueData]
    debt: DebtMovementData
    financing: list[FinancingSplitData]
    reconciles: bool
    discrepancies: list[DiscrepancyData]

    @classmethod
    def from_entity(cls, report: MonthEndReport) -> MonthEndReportData:
        return cls(
            period=PeriodData.from_entity(report.period),
            location_id=report.location_id,
            figures=AccrualFiguresData.from_entity(report.figures),
            som=(
                None if report.som is None else SomFiguresData.from_entity(report.som)
            ),
            closing_by_location=[
                LocationInventoryValueData.from_entity(entry)
                for entry in report.closing_by_location
            ],
            debt=DebtMovementData.from_entity(report.debt),
            financing=[
                FinancingSplitData.from_entity(row) for row in report.financing
            ],
            reconciles=report.reconciles,
            discrepancies=[
                DiscrepancyData.from_entity(found) for found in report.discrepancies
            ],
        )
