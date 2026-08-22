"""``SalesInvoice`` and its lines — PRD §5.4, FR-2.7, FR-4.5b, FR-4.5e.

Every rule here is a pure function of the invoice's own lines. Whether a
price still *resolves* is not, because that needs the live unit and the
live catalog row, so it lives in ``InvoicePoster`` and is tested against
the application harness instead. Nothing below imports a repository or
awaits anything.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from domain.entities import SalesInvoice, SalesInvoiceLine
from domain.enums import DocumentStatus, PaymentType, TrackingType
from domain.errors import (
    AnonymousDebtError,
    CreditTermsError,
    CurrencyMismatchError,
    DocumentNotConfirmedError,
    DocumentNotDraftError,
    DuplicateScanError,
    EmptyInvoiceError,
    InvalidMoneyError,
)
from domain.value_objects import Currency, Money

NOW = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def uzs(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def phone_line(invoice_id: UUID | None = None, **overrides: object) -> SalesInvoiceLine:
    fields: dict[str, object] = {
        "id": uuid4(),
        "sales_invoice_id": invoice_id or uuid4(),
        "product_id": uuid4(),
        "device_unit_id": uuid4(),
        "quantity": 1,
        "currency": Currency.USD,
        "tracking_type": TrackingType.SERIAL,
    }
    fields.update(overrides)
    return SalesInvoiceLine(**fields)  # type: ignore[arg-type]


def case_line(invoice_id: UUID | None = None, **overrides: object) -> SalesInvoiceLine:
    fields: dict[str, object] = {
        "id": uuid4(),
        "sales_invoice_id": invoice_id or uuid4(),
        "product_id": uuid4(),
        "device_unit_id": None,
        "quantity": 2,
        "currency": Currency.UZS,
        "tracking_type": TrackingType.QUANTITY,
    }
    fields.update(overrides)
    return SalesInvoiceLine(**fields)  # type: ignore[arg-type]


def invoice(
    *lines: SalesInvoiceLine,
    status: DocumentStatus = DocumentStatus.DRAFT,
    **terms: object,
):
    return SalesInvoice(
        id=uuid4(),
        number="INV-2026-0001",
        status=status,
        location_id=uuid4(),
        created_by=uuid4(),
        created_at=NOW,
        lines=list(lines),
        **terms,  # type: ignore[arg-type]
    )


class TestALineDescribesSomethingSellable:
    def test_a_serialized_line_must_name_the_handset_it_sells(self):
        with pytest.raises(InvalidMoneyError):
            phone_line(device_unit_id=None)

    def test_a_serialized_line_sells_exactly_one_handset(self):
        with pytest.raises(InvalidMoneyError):
            phone_line(quantity=2)

    def test_a_quantity_line_names_no_handset(self):
        with pytest.raises(InvalidMoneyError):
            case_line(device_unit_id=uuid4())

    def test_a_line_for_nothing_sells_nothing(self):
        with pytest.raises(InvalidMoneyError):
            case_line(quantity=0)


class TestAPriceIsPositiveAndInTheProductsCurrency:
    def test_a_negative_override_is_refused(self):
        """FR-4.5e: a giveaway is a zero-priced line, and money flowing the
        other way is a return, not a sale."""
        with pytest.raises(InvalidMoneyError):
            phone_line(override_price=usd("-10"))

    def test_a_giveaway_is_allowed_at_zero(self):
        assert phone_line(override_price=usd("0")).override_price == usd("0")

    def test_a_price_in_another_currency_is_refused(self):
        """§4.5 rule 3: the line is denominated by its product."""
        with pytest.raises(CurrencyMismatchError):
            phone_line(override_price=uzs("500000"))

    def test_an_approver_without_an_override_is_refused(self):
        """FR-4.5f: the name records who approved a difference — there is
        no difference to attribute when nobody overrode anything."""
        with pytest.raises(InvalidMoneyError):
            phone_line(price_approved_by=uuid4())


class TestADraftReservesNoPrice:
    """FR-4.5b1, expressed structurally: both snapshots stay null until
    confirm, so there is no scan-time figure for anything to freeze."""

    def test_a_scanned_line_holds_neither_snapshot(self):
        line = phone_line()
        assert line.resolved_price is None
        assert line.charged_price is None
        assert line.line_total is None

    def test_an_unoverridden_line_charges_what_was_resolved_at_confirm(self):
        line = phone_line()
        line.snapshot(usd("480"))
        assert line.charged_price == usd("480")
        assert line.is_deviation is False

    def test_an_override_survives_re_resolution_and_reports_the_deviation(self):
        """§4.5b's stated consequence: the deviation is measured against
        the shelf price at the moment of sale, not against what the
        Manager was looking at."""
        manager = uuid4()
        line = phone_line()
        line.override(usd("300"), manager)
        line.snapshot(usd("480"))

        assert line.charged_price == usd("300")
        assert line.resolved_price == usd("480")
        assert line.is_deviation is True
        assert line.price_approved_by == manager

    def test_clearing_an_override_takes_the_approver_with_it(self):
        line = phone_line()
        line.override(usd("300"), uuid4(), "haggled")
        line.override(None, uuid4())

        assert line.override_price is None
        assert line.price_approved_by is None
        assert line.price_note is None

    def test_a_cleared_override_charges_the_resolved_price_again(self):
        line = phone_line()
        line.override(usd("300"), uuid4())
        line.override(None, uuid4())
        line.snapshot(usd("520"))

        assert line.charged_price == usd("520")
        assert line.is_deviation is False


class TestOneSubtotalPerCurrency:
    """FR-2.7, §4.5 rule 4: no field anywhere holds their sum."""

    def test_a_phone_and_an_accessory_report_two_figures(self):
        phone, case = phone_line(), case_line()
        phone.snapshot(usd("600"))
        case.snapshot(uzs("25000"))

        totals = invoice(phone, case).subtotals()

        assert totals == {Currency.USD: usd("600"), Currency.UZS: uzs("50000")}

    def test_a_draft_reports_nothing_because_it_has_no_prices(self):
        assert invoice(phone_line(), case_line()).subtotals() == {}

    def test_two_lines_in_one_currency_are_added_to_each_other(self):
        first, second = phone_line(), phone_line()
        first.snapshot(usd("600"))
        second.snapshot(usd("400"))

        assert invoice(first, second).subtotals() == {Currency.USD: usd("1000")}


class TestConfirmingChecksWhatTheInvoiceItselfKnows:
    def test_an_empty_invoice_is_refused(self):
        with pytest.raises(EmptyInvoiceError):
            invoice().confirm(NOW, uuid4())

    def test_the_same_handset_twice_is_refused(self):
        unit_id = uuid4()
        doubled = invoice(
            phone_line(device_unit_id=unit_id), phone_line(device_unit_id=unit_id)
        )
        with pytest.raises(DuplicateScanError):
            doubled.confirm(NOW, uuid4())

    def test_confirming_records_who_and_when(self):
        seller = uuid4()
        sale = invoice(phone_line())
        sale.confirm(NOW, seller)

        assert sale.status is DocumentStatus.CONFIRMED
        assert sale.confirmed_by == seller
        assert sale.confirmed_at == NOW

    def test_confirming_twice_is_refused(self):
        sale = invoice(phone_line())
        sale.confirm(NOW, uuid4())
        with pytest.raises(DocumentNotDraftError):
            sale.confirm(NOW, uuid4())


class TestCancellingIsOnceAndOnlyAfterConfirm:
    def test_a_draft_cannot_be_cancelled(self):
        """§4.4: there is nothing to compensate — a draft wrote nothing."""
        with pytest.raises(DocumentNotConfirmedError):
            invoice(phone_line()).cancel(NOW, uuid4())

    def test_cancelling_twice_is_refused(self):
        """The only guard against a double reversal: ``LedgerPoster.reverse``
        deliberately holds none of its own."""
        sale = invoice(phone_line())
        sale.confirm(NOW, uuid4())
        sale.cancel(NOW, uuid4(), "customer changed their mind")

        with pytest.raises(DocumentNotConfirmedError):
            sale.cancel(NOW, uuid4())


class TestDeviationsAreWhatTheReportReads:
    def test_only_confirmed_lines_charged_off_the_resolved_price_count(self):
        """FR-9.7's input, and FR-4.5b1's promise that a markdown made
        while the draft sat open reports no deviation."""
        followed, overridden, still_draft = phone_line(), phone_line(), phone_line()
        followed.snapshot(usd("480"))
        overridden.override(usd("300"), uuid4())
        overridden.snapshot(usd("480"))

        deviations = invoice(followed, overridden, still_draft).deviations()

        assert deviations == [overridden]


class TestEachPaymentTypeAdmitsOneShapeOfTerms:
    """§4.7: the three ways a phone leaves the store, and what each one
    may say about the money."""

    def test_a_cash_sale_names_no_credit_company(self):
        with pytest.raises(CreditTermsError):
            invoice(phone_line(), credit_company_id=uuid4())

    def test_a_cash_sale_carries_no_debt(self):
        with pytest.raises(CreditTermsError):
            invoice(phone_line(), debt=uzs("7800000"))

    def test_a_financed_sale_names_its_company(self):
        with pytest.raises(CreditTermsError):
            invoice(phone_line(), payment_type=PaymentType.CREDIT_COMPANY)

    def test_a_financed_sale_opens_no_debt(self):
        """FR-11.4: the company pays the store in full at sale time."""
        with pytest.raises(CreditTermsError):
            invoice(
                phone_line(),
                payment_type=PaymentType.CREDIT_COMPANY,
                credit_company_id=uuid4(),
                debt=uzs("7800000"),
            )

    def test_a_financed_sale_may_record_a_contract_reference(self):
        sale = invoice(
            phone_line(),
            payment_type=PaymentType.CREDIT_COMPANY,
            credit_company_id=uuid4(),
            contract_ref="UZ-99417",
        )

        assert sale.contract_ref == "UZ-99417"

    def test_a_store_credit_sale_states_its_debt(self):
        with pytest.raises(CreditTermsError):
            invoice(
                phone_line(),
                payment_type=PaymentType.STORE_CREDIT,
                customer_id=uuid4(),
            )

    def test_a_debt_of_zero_is_a_sale_that_was_paid_for(self):
        with pytest.raises(CreditTermsError):
            invoice(
                phone_line(),
                payment_type=PaymentType.STORE_CREDIT,
                customer_id=uuid4(),
                debt=uzs("0"),
            )

    def test_the_debt_is_written_in_som_whatever_the_lines_cost(self):
        """§4.7: a $600 phone's debt is 7 800 000 so'm, with no rate
        recorded anywhere."""
        with pytest.raises(CurrencyMismatchError):
            invoice(
                phone_line(),
                payment_type=PaymentType.STORE_CREDIT,
                customer_id=uuid4(),
                debt=usd("600"),
            )

    def test_the_store_does_not_lend_and_finance_the_same_sale(self):
        with pytest.raises(CreditTermsError):
            invoice(
                phone_line(),
                payment_type=PaymentType.STORE_CREDIT,
                customer_id=uuid4(),
                credit_company_id=uuid4(),
                debt=uzs("7800000"),
            )


class TestStoreCreditNamesTheDebtor:
    """§4.7: an invoice may be raised for a walk-in (FR-4.1), but a debt
    cannot — it would be money the store knows it is owed and cannot say by
    whom."""

    def test_lending_to_nobody_is_refused(self):
        with pytest.raises(AnonymousDebtError):
            invoice(
                phone_line(),
                payment_type=PaymentType.STORE_CREDIT,
                debt=uzs("7800000"),
            )

    def test_a_walk_in_may_still_pay_cash(self):
        sale = invoice(phone_line())

        assert sale.customer_id is None
        assert sale.payment_type is PaymentType.PAID_IN_FULL

    def test_a_walk_in_may_still_be_financed(self):
        """FR-11.4: a financed sale is settled at confirm and differs from
        cash only by a label."""
        sale = invoice(
            phone_line(),
            payment_type=PaymentType.CREDIT_COMPANY,
            credit_company_id=uuid4(),
        )

        assert sale.customer_id is None


class TestTermsAreStatedWhileTheInvoiceIsStillADraft:
    def test_set_terms_replaces_what_the_draft_carried(self):
        customer = uuid4()
        sale = invoice(phone_line(), customer_id=customer)

        sale.set_terms(PaymentType.STORE_CREDIT, debt=uzs("7800000"))

        assert sale.payment_type is PaymentType.STORE_CREDIT
        assert sale.debt == uzs("7800000")

    def test_switching_back_to_cash_clears_the_debt(self):
        sale = invoice(phone_line(), customer_id=uuid4())
        sale.set_terms(PaymentType.STORE_CREDIT, debt=uzs("7800000"))

        sale.set_terms(PaymentType.PAID_IN_FULL)

        assert sale.debt is None

    def test_a_confirmed_sale_cannot_be_re_termed(self):
        """§4.4: the debt is already open and the ledger already written."""
        sale = invoice(phone_line(), customer_id=uuid4())
        sale.confirm(NOW, uuid4())

        with pytest.raises(DocumentNotDraftError):
            sale.set_terms(PaymentType.STORE_CREDIT, debt=uzs("7800000"))

    def test_confirming_checks_the_terms_too(self):
        """A draft saved through some other path still cannot confirm into
        an anonymous debt."""
        sale = invoice(phone_line(), customer_id=uuid4())
        sale.set_terms(PaymentType.STORE_CREDIT, debt=uzs("7800000"))
        sale.customer_id = None

        with pytest.raises(AnonymousDebtError):
            sale.confirm(NOW, uuid4())
