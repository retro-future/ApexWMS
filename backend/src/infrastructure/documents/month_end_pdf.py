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
from application.localization.locale import Locale
from application.services.cost_pools import INVENTORY_SIGN
from domain.enums import PaymentType, TransactionType
from domain.value_objects import Currency, CurrencyTotals, Money
from infrastructure.documents.page import DocumentPage, DocumentPageFactory

_LABEL = 60.0
_AMOUNT = 40.0
_PAYMENT_TYPE_KEY = {
    PaymentType.PAID_IN_FULL: "me_paid_in_full",
    PaymentType.CREDIT_COMPANY: "me_credit_company",
    PaymentType.STORE_CREDIT: "me_store_credit",
}
# The moves between opening and closing inventory, each with the transaction
# type whose ``INVENTORY_SIGN`` turns its stored cash amount into a shelf move.
_STOCK_MOVE_ROWS: tuple[tuple[str, str, TransactionType], ...] = (
    ("me_purchases", "purchases", TransactionType.PURCHASE),
    ("me_cogs", "cost_of_goods", TransactionType.COGS),
    ("me_write_offs", "write_offs", TransactionType.WRITE_OFF_LOSS),
    ("me_returned", "supplier_return_credits", TransactionType.SUPPLIER_RETURN_CREDIT),
    ("me_count_adjustments", "count_adjustments", TransactionType.COUNT_ADJUSTMENT),
)


class PdfMonthEndReportRenderer:
    def __init__(self, pages: DocumentPageFactory) -> None:
        self._pages = pages

    def render(
        self, report: MonthEndReport, letterhead: Letterhead, locale: Locale
    ) -> bytes:
        page = self._pages.page(locale)
        page.start_at(report.period.end)
        page.letterhead(letterhead)
        month = page.t(f"me_month_{report.period.month}")
        page.title(
            page.t("me_title", month=month, year=report.period.year),
            page.t(
                "me_period",
                start=f"{report.period.start:%Y-%m-%d %H:%M}",
                end=f"{report.period.end:%Y-%m-%d %H:%M}",
                timezone=report.period.timezone,
            ),
        )
        currencies = self._currencies(report.figures)
        heads = ("", *(c.value for c in currencies))
        widths = (_LABEL, *(_AMOUNT for _ in currencies))

        page.title(page.t("me_stock_value"))
        page.table(heads, widths, self._stock_rows(page, report.figures, currencies))
        if not report.figures.supplier_return_credits.is_empty:
            page.title(page.t("me_supplier_refunds"))
            page.table(heads, widths, self._refund_rows(page, report.figures, currencies))
        page.title(page.t("me_sales"))
        page.table(heads, widths, self._sales_rows(page, report.figures, currencies))

        page.title(page.t("me_closing_by_location"))
        page.table(
            (page.t("me_location"), page.t("me_units"), page.t("me_value")),
            (_LABEL, 25.0, 75.0),
            self._location_rows(report.closing_by_location),
        )
        page.title(page.t("me_debt_and_cash"))
        page.table(
            ("", page.t("me_amount")), (_LABEL, 75.0), self._debt_rows(page, report.debt)
        )
        page.title(page.t("me_financing"))
        page.table(
            (page.t("me_type"), page.t("me_invoices"), page.t("me_revenue")),
            (_LABEL, 25.0, 75.0),
            self._financing_rows(page, report.financing),
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
        page: DocumentPage,
        figures: AccrualFigures,
        currencies: tuple[Currency, ...],
    ) -> list[tuple[str, ...]]:
        """Opening to closing, every move signed for the shelf (§4.6 trap)."""
        rows: list[tuple[str, ...]] = [
            (
                page.t("me_opening_inventory"),
                *(figures.opening_inventory.of(c).format() for c in currencies),
            )
        ]
        for label_key, attr, txn_type in _STOCK_MOVE_ROWS:
            totals: CurrencyTotals = getattr(figures, attr)
            sign = INVENTORY_SIGN[txn_type]
            rows.append(
                (page.t(label_key), *((totals.of(c) * sign).format() for c in currencies))
            )
        rows.append(
            (
                page.t("me_closing_inventory"),
                *(figures.closing_inventory.of(c).format() for c in currencies),
            )
        )
        return rows

    @staticmethod
    def _refund_rows(
        page: DocumentPage,
        figures: AccrualFigures,
        currencies: tuple[Currency, ...],
    ) -> list[tuple[str, ...]]:
        """The credit the supplier gave for goods the bridge already removed."""
        return [
            (
                page.t("me_supplier_return_credit"),
                *(
                    figures.supplier_return_credits.of(c).format()
                    for c in currencies
                ),
            )
        ]

    @staticmethod
    def _sales_rows(
        page: DocumentPage,
        figures: AccrualFigures,
        currencies: tuple[Currency, ...],
    ) -> list[tuple[str, ...]]:
        """The plain profit view: revenue in, cost out, margin their sum."""
        margin = figures.margin
        percent = figures.margin_percent
        return [
            (
                page.t("me_sales_revenue"),
                *(figures.revenue.of(c).format() for c in currencies),
            ),
            (
                page.t("me_cogs"),
                *(figures.cost_of_goods.of(c).format() for c in currencies),
            ),
            (
                page.t("me_gross_margin"),
                *(margin.get(c, Money.zero(c)).format() for c in currencies),
            ),
            (
                page.t("me_margin_percent"),
                *(
                    page.t("me_na") if percent.get(c) is None else f"{percent[c]}%"
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
    def _debt_rows(page: DocumentPage, debt: DebtMovement) -> list[tuple[str, str]]:
        return [
            (page.t("me_opening_debt"), debt.opening.format()),
            (page.t("me_booked"), debt.booked.format()),
            (page.t("me_collected"), debt.collected.format()),
            (page.t("me_voided"), debt.voided.format()),
            (page.t("me_closing_debt"), debt.closing.format()),
        ]

    @staticmethod
    def _financing_rows(
        page: DocumentPage, rows: list[FinancingSplitRow]
    ) -> list[tuple[str, str, str]]:
        return [
            (
                row.credit_company_name or page.t(_PAYMENT_TYPE_KEY[row.payment_type]),
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
        page.title(page.t("me_reconciliation"))
        page.table(
            (page.t("me_subject"), page.t("me_ledger"), page.t("me_stock")),
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
