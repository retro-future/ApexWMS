"""The month-end close, on paper (FR-10.9, PRD §5.10).

Small tables rather than one wide one, because the report is several
different questions and a single grid would put a som debt figure in the
same column as a dollar margin. Each row prints one amount per currency the
period touched, side by side and never summed (§4.5 rule 4).

The **stock value** table rolls opening inventory to closing, and shows
every move in the inventory direction via ``INVENTORY_SIGN`` — a purchase
reads as goods coming in, a supplier return as goods leaving. The credit
that came back for a return is its own note. The **sales** table keeps
§4.6's cash signs, because there revenue in and cost out is the point.

The creation date is pinned to the period's end, so re-running March's
report months later is byte-identical (FR-10.10) — the same trick, for the
same reason, as ``DocumentPage.start`` pinning to a confirm timestamp.
"""

from application.dtos import (
    AccrualFigures,
    DebtMovement,
    FinancingSplitRow,
    Letterhead,
    LocationInventoryValue,
    MonthEndReport,
)
from application.services.cost_pools import INVENTORY_SIGN
from domain.enums import PaymentType, TransactionType
from domain.value_objects import Currency, CurrencyTotals, Money
from infrastructure.documents.page import DocumentPage, DocumentPageFactory

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_LABEL = 60.0
_AMOUNT = 40.0
# The page is English-only (the core font is Latin-1), so the enum value is
# spelled out here rather than translated the way the screen does it.
_PAYMENT_TYPES = {
    PaymentType.PAID_IN_FULL: "Paid in full",
    PaymentType.CREDIT_COMPANY: "Credit company",
    PaymentType.STORE_CREDIT: "Store credit",
}
# The moves between opening and closing inventory, each with the transaction
# type whose ``INVENTORY_SIGN`` turns its stored cash amount into a shelf move.
_STOCK_MOVE_ROWS: tuple[tuple[str, str, TransactionType], ...] = (
    ("Purchases", "purchases", TransactionType.PURCHASE),
    ("Cost of goods sold", "cost_of_goods", TransactionType.COGS),
    ("Write-offs", "write_offs", TransactionType.WRITE_OFF_LOSS),
    (
        "Returned to suppliers",
        "supplier_return_credits",
        TransactionType.SUPPLIER_RETURN_CREDIT,
    ),
    ("Count adjustments", "count_adjustments", TransactionType.COUNT_ADJUSTMENT),
)


class PdfMonthEndReportRenderer:
    def __init__(self, pages: DocumentPageFactory) -> None:
        self._pages = pages

    def render(self, report: MonthEndReport, letterhead: Letterhead) -> bytes:
        page = self._pages.page()
        page.start_at(report.period.end)
        page.letterhead(letterhead)
        page.title(
            f"Month-End Report  {_MONTHS[report.period.month - 1]} {report.period.year}",
            f"Period {report.period.start:%Y-%m-%d %H:%M} to "
            f"{report.period.end:%Y-%m-%d %H:%M} ({report.period.timezone})",
        )
        currencies = self._currencies(report.figures)
        heads = ("", *(c.value for c in currencies))
        widths = (_LABEL, *(_AMOUNT for _ in currencies))

        page.title("Stock value")
        page.table(heads, widths, self._stock_rows(report.figures, currencies))
        if not report.figures.supplier_return_credits.is_empty:
            page.title("Supplier returns: money back")
            page.table(heads, widths, self._refund_rows(report.figures, currencies))
        page.title("Sales")
        page.table(heads, widths, self._sales_rows(report.figures, currencies))

        page.title("Closing inventory by location")
        page.table(
            ("Location", "Units", "Value"),
            (_LABEL, 25.0, 75.0),
            self._location_rows(report.closing_by_location),
        )
        page.title("Customer debt and cash collected")
        page.table(
            ("", "Amount"), (_LABEL, 75.0), self._debt_rows(report.debt)
        )
        page.title("Sales by financing type")
        page.table(
            ("Type", "Invoices", "Revenue"),
            (_LABEL, 25.0, 75.0),
            self._financing_rows(report.financing),
        )
        self._reconciliation(page, report)
        return page.output()

    @staticmethod
    def _currencies(figures: AccrualFigures) -> tuple[Currency, ...]:
        """The currencies the period actually touched, in a stable order."""
        touched: set[Currency] = set()
        for totals in (
            figures.opening_inventory,
            figures.purchases,
            figures.cost_of_goods,
            figures.revenue,
            figures.write_offs,
            figures.supplier_return_credits,
            figures.count_adjustments,
            figures.closing_inventory,
        ):
            touched |= totals.currencies
        return tuple(sorted(touched, key=lambda one: one.value))

    @staticmethod
    def _stock_rows(
        figures: AccrualFigures, currencies: tuple[Currency, ...]
    ) -> list[tuple[str, ...]]:
        """Opening to closing, every move signed for the shelf (§4.6 trap)."""
        rows: list[tuple[str, ...]] = [
            (
                "Opening inventory",
                *(figures.opening_inventory.of(c).format() for c in currencies),
            )
        ]
        for label, attr, txn_type in _STOCK_MOVE_ROWS:
            totals: CurrencyTotals = getattr(figures, attr)
            sign = INVENTORY_SIGN[txn_type]
            rows.append(
                (label, *((totals.of(c) * sign).format() for c in currencies))
            )
        rows.append(
            (
                "Closing inventory",
                *(figures.closing_inventory.of(c).format() for c in currencies),
            )
        )
        return rows

    @staticmethod
    def _refund_rows(
        figures: AccrualFigures, currencies: tuple[Currency, ...]
    ) -> list[tuple[str, ...]]:
        """The credit the supplier gave for goods the bridge already removed."""
        return [
            (
                "Supplier return credit",
                *(
                    figures.supplier_return_credits.of(c).format()
                    for c in currencies
                ),
            )
        ]

    @staticmethod
    def _sales_rows(
        figures: AccrualFigures, currencies: tuple[Currency, ...]
    ) -> list[tuple[str, ...]]:
        """The plain profit view: revenue in, cost out, margin their sum."""
        margin = figures.margin
        percent = figures.margin_percent
        return [
            (
                "Sales revenue",
                *(figures.revenue.of(c).format() for c in currencies),
            ),
            (
                "Cost of goods sold",
                *(figures.cost_of_goods.of(c).format() for c in currencies),
            ),
            (
                "Gross margin",
                *(margin.get(c, Money.zero(c)).format() for c in currencies),
            ),
            (
                "Margin %",
                *(
                    "n/a" if percent.get(c) is None else f"{percent[c]}%"
                    for c in currencies
                ),
            ),
        ]

    @staticmethod
    def _location_rows(
        places: list[LocationInventoryValue],
    ) -> list[tuple[str, str, str]]:
        return [
            (
                entry.location_name or str(entry.location_id),
                str(entry.quantity),
                _side_by_side(entry.value),
            )
            for entry in places
        ]

    @staticmethod
    def _debt_rows(debt: DebtMovement) -> list[tuple[str, str]]:
        return [
            ("Opening debt", debt.opening.format()),
            ("Store-credit sales booked", debt.booked.format()),
            ("Cash collected", debt.collected.format()),
            ("Debt voided by cancellation", debt.voided.format()),
            ("Closing debt outstanding", debt.closing.format()),
        ]

    @staticmethod
    def _financing_rows(rows: list[FinancingSplitRow]) -> list[tuple[str, str, str]]:
        return [
            (
                row.credit_company_name or _PAYMENT_TYPES[row.payment_type],
                str(row.invoice_count),
                row.revenue.format(),
            )
            for row in rows
        ]

    @staticmethod
    def _reconciliation(page: DocumentPage, report: MonthEndReport) -> None:
        """FR-10.7: a mismatch prints. A report that reconciled says nothing,
        because a clean sweep is the expected state, not news."""
        if report.reconciles:
            return
        page.title("Reconciliation")
        page.table(
            ("Subject", "Ledger", "Stock"),
            (_LABEL, 55.0, 55.0),
            [
                (found.subject, found.expected, found.found)
                for found in report.discrepancies
            ],
        )


def _side_by_side(totals: CurrencyTotals) -> str:
    """One cell, one amount per currency — never their sum (§4.5 rule 4)."""
    return "   ".join(
        amount.format()
        for _, amount in sorted(totals.as_dict().items(), key=lambda pair: pair[0].value)
    )
