"""The printed month-end close, block by block (FR-10.9, PRD §5.10).

The screen and the page tell the same story: a stock-value bridge where
every move is shown in the *inventory* direction, so a supplier return
reads as goods leaving (``-``), and a separate note for the credit that
came back for them.
"""

from datetime import UTC, datetime

from application.dtos import (
    AccrualFigures,
    DebtMovement,
    Letterhead,
    MonthEndReport,
    Period,
)
from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale
from domain.value_objects import Currency, CurrencyTotals, Money
from infrastructure.documents.month_end_pdf import PdfMonthEndReportRenderer
from infrastructure.documents.page import DocumentPageFactory
from tests.api.pdf_helpers import pdf_text

_USD = Currency.USD


def _usd(minor: int) -> CurrencyTotals:
    return CurrencyTotals.empty().add(Money(minor, _USD))


def _report(figures: AccrualFigures) -> MonthEndReport:
    zero = Money.zero(Currency.UZS)
    return MonthEndReport(
        period=Period(
            year=2026,
            month=8,
            timezone="Asia/Tashkent",
            start=datetime(2026, 7, 31, 19, tzinfo=UTC),
            end=datetime(2026, 8, 31, 19, tzinfo=UTC),
        ),
        location_id=None,
        figures=figures,
        closing_by_location=[],
        debt=DebtMovement(zero, zero, zero, zero, zero),
        financing=[],
        discrepancies=[],
    )


def _render(figures: AccrualFigures) -> str:
    renderer = PdfMonthEndReportRenderer(DocumentPageFactory(MessageCatalog()))
    return pdf_text(renderer.render(_report(figures), Letterhead(), Locale.EN))


def test_the_page_still_names_its_period_and_its_totals():
    text = _render(AccrualFigures(revenue=_usd(50000), cost_of_goods=_usd(-30000)))

    assert "Month-End Report" in text
    assert "August 2026" in text
    assert "Closing inventory" in text
    assert "Gross margin" in text


def test_a_purchase_reads_as_stock_coming_in_not_money_leaving():
    text = _render(
        AccrualFigures(
            purchases=_usd(-200000),
            closing_inventory=_usd(200000),
        )
    )

    assert "$2,000.00" in text
    assert "-$2,000.00" not in text


def test_a_supplier_return_reads_as_goods_leaving_the_shelf():
    text = _render(
        AccrualFigures(
            purchases=_usd(-200000),
            supplier_return_credits=_usd(90000),
            closing_inventory=_usd(110000),
        )
    )

    # -$900 in the bridge where the goods left; +$900 as the credit for them.
    assert "-$900.00" in text
    assert "$900.00" in text
    assert "money back" in text.lower()


def test_the_credit_note_is_left_out_when_no_return_happened():
    text = _render(AccrualFigures(purchases=_usd(-200000), closing_inventory=_usd(200000)))

    assert "money back" not in text.lower()
