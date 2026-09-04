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
)
from application.models.currency_subtotal import CurrencySubtotalData
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
    opening_inventory: list[CurrencySubtotalData]
    purchases: list[CurrencySubtotalData]
    cost_of_goods: list[CurrencySubtotalData]
    revenue: list[CurrencySubtotalData]
    # Negative: money handed back to customers (FR-4.9).
    sales_returns: list[CurrencySubtotalData]
    write_offs: list[CurrencySubtotalData]
    supplier_return_credits: list[CurrencySubtotalData]
    count_adjustments: list[CurrencySubtotalData]
    closing_inventory: list[CurrencySubtotalData]
    margin: list[CurrencySubtotalData]
    margin_percent: list[MarginPercentData]

    @classmethod
    def from_entity(cls, figures: AccrualFigures) -> AccrualFiguresData:
        return cls(
            opening_inventory=CurrencySubtotalData.from_entity(
                figures.opening_inventory.as_dict()
            ),
            purchases=CurrencySubtotalData.from_entity(figures.purchases.as_dict()),
            cost_of_goods=CurrencySubtotalData.from_entity(
                figures.cost_of_goods.as_dict()
            ),
            revenue=CurrencySubtotalData.from_entity(figures.revenue.as_dict()),
            sales_returns=CurrencySubtotalData.from_entity(
                figures.sales_returns.as_dict()
            ),
            write_offs=CurrencySubtotalData.from_entity(figures.write_offs.as_dict()),
            supplier_return_credits=CurrencySubtotalData.from_entity(
                figures.supplier_return_credits.as_dict()
            ),
            count_adjustments=CurrencySubtotalData.from_entity(
                figures.count_adjustments.as_dict()
            ),
            closing_inventory=CurrencySubtotalData.from_entity(
                figures.closing_inventory.as_dict()
            ),
            margin=CurrencySubtotalData.from_entity(figures.margin),
            margin_percent=MarginPercentData.from_entity(figures),
        )


class LocationInventoryValueData(CamelModel):
    location_id: UUID
    location_name: str | None
    quantity: int
    value: list[CurrencySubtotalData]

    @classmethod
    def from_entity(cls, entry: LocationInventoryValue) -> LocationInventoryValueData:
        return cls(
            location_id=entry.location_id,
            location_name=entry.location_name,
            quantity=entry.quantity,
            value=CurrencySubtotalData.from_entity(entry.value.as_dict()),
        )


class DebtMovementData(CamelModel):
    """Always som, and always store-wide — debt belongs to a customer, not
    a shelf, so a location-scoped report does not narrow it."""

    opening_minor: int
    booked_minor: int
    collected_minor: int
    voided_minor: int
    # Debt written off by confirmed customer returns (FR-4.9d).
    relieved_minor: int
    closing_minor: int
    currency: Currency

    @classmethod
    def from_entity(cls, debt: DebtMovement) -> DebtMovementData:
        return cls(
            opening_minor=debt.opening.amount_minor,
            booked_minor=debt.booked.amount_minor,
            collected_minor=debt.collected.amount_minor,
            voided_minor=debt.voided.amount_minor,
            relieved_minor=debt.relieved.amount_minor,
            closing_minor=debt.closing.amount_minor,
            currency=debt.closing.currency,
        )


class FinancingSplitData(CamelModel):
    payment_type: PaymentType
    credit_company_id: UUID | None
    credit_company_name: str | None
    invoice_count: int
    revenue: list[CurrencySubtotalData]

    @classmethod
    def from_entity(cls, row: FinancingSplitRow) -> FinancingSplitData:
        return cls(
            payment_type=row.payment_type,
            credit_company_id=row.credit_company_id,
            credit_company_name=row.credit_company_name,
            invoice_count=row.invoice_count,
            revenue=CurrencySubtotalData.from_entity({row.revenue.currency: row.revenue}),
        )


class DiscrepancyData(CamelModel):
    subject: str
    expected: str
    found: str

    @classmethod
    def from_entity(cls, found: Discrepancy) -> DiscrepancyData:
        return cls(subject=found.subject, expected=found.expected, found=found.found)


class MonthEndReportData(CamelModel):
    period: PeriodData
    location_id: UUID | None
    figures: AccrualFiguresData
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
