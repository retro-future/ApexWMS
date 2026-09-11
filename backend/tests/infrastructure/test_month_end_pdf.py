"""The printed month-end close, block by block (FR-10.9, PRD §5.10).

The screen and the page tell the same story: a stock-value bridge where
every move is shown in the *inventory* direction, so a supplier return
reads as goods leaving (``-``), and a separate note for the credit that
came back for them.
"""

from datetime import UTC, datetime
from decimal import Decimal

from application.dtos import (
    AccrualFigures,
    ConversionBasis,
    DebtMovement,
    Letterhead,
    MonthEndReport,
    Period,
    SomFigures,
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


def _report(
    figures: AccrualFigures, som: SomFigures | None = None
) -> MonthEndReport:
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
        som=som,
        closing_by_location=[],
        debt=DebtMovement(zero, zero, zero, zero, zero, zero),
        financing=[],
        discrepancies=[],
    )


def _render(figures: AccrualFigures, som: SomFigures | None = None) -> str:
    renderer = PdfMonthEndReportRenderer(DocumentPageFactory(MessageCatalog()))
    return pdf_text(renderer.render(_report(figures, som), Letterhead(), Locale.EN))


def _som(
    revenue: int,
    cost: int,
    *,
    gain: int = 0,
    instalments: int = 0,
    before_the_log: bool = False,
) -> SomFigures:
    zero = Money.zero(Currency.UZS)
    return SomFigures(
        opening_inventory=zero,
        purchases=zero,
        cost_of_goods=Money(cost, Currency.UZS),
        revenue=Money(revenue, Currency.UZS),
        sales_returns=zero,
        write_offs=zero,
        supplier_return_credits=zero,
        count_adjustments=zero,
        closing_inventory=zero,
        rate_gain=Money(gain, Currency.UZS),
        instalment_income=Money(instalments, Currency.UZS),
        basis=ConversionBasis(
            opening_rate=Decimal("12000"),
            closing_rate=Decimal("12500"),
            before_the_first_quote=before_the_log,
        ),
    )


def test_a_store_with_no_rate_prints_no_som_block():
    assert "The month in so'm" not in _render(_usd_figures())


def test_the_som_block_prints_its_figures_and_the_rates_behind_them():
    printed = _render(_usd_figures(), _som(7_500_000, -4_560_000))

    assert "The month in so'm" in printed
    assert "12000 at the start of the period, 12500 at the end" in printed
    assert "7 500 000 so'm" in printed.replace(" ", " ")


def test_it_says_when_the_period_predates_the_first_rate():
    printed = _render(_usd_figures(), _som(7_500_000, -4_560_000, before_the_log=True))

    assert "earlier than the first rate" in printed


def _usd_figures() -> AccrualFigures:
    return AccrualFigures(revenue=_usd(60000), cost_of_goods=_usd(-38000))


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


def test_the_profit_line_adds_both_gains_to_the_margin():
    """The one number an owner checks against their own arithmetic."""
    printed = _render(
        _usd_figures(),
        _som(7_500_000, -4_125_000, gain=645_000, instalments=300_000),
    )

    assert "Rate gain" in printed
    assert "645 000 so'm" in printed
    assert "Instalment income" in printed
    assert "300 000 so'm" in printed
    assert "4 320 000 so'm" in printed
