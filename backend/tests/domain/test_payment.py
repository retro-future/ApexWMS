"""What a payment can and cannot be — PRD §4.7, FR-11.6, FR-11.8.

No repository here. Everything below is a fact about one row, which is
what makes ``Payment`` the right place to enforce it: a payment recorded
in dollars, or a reversal that gives money back twice, is wrong however it
reached the constructor.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.entities import Payment
from domain.enums import PaymentMethod
from domain.errors import (
    CurrencyMismatchError,
    InvalidMoneyError,
    PaymentAlreadyReversedError,
)
from domain.value_objects import Currency, Money

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def som(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def a_payment(**overrides) -> Payment:
    fields = {
        "sales_invoice_id": uuid4(),
        "occurred_at": NOW,
        "amount": som("800000"),
        "method": PaymentMethod.CASH,
        "user_id": uuid4(),
    }
    return Payment(**{**fields, **overrides})


class TestEveryPaymentIsWrittenInSom:
    """§4.7: the seller quotes a som total for a dollar-priced phone, and
    that figure *is* the debt — no rate is recorded anywhere."""

    def test_a_som_payment_is_accepted(self):
        payment = a_payment(amount=som("800000"))

        assert payment.amount == som("800000")

    def test_a_dollar_payment_is_refused(self):
        with pytest.raises(CurrencyMismatchError):
            a_payment(amount=Money.from_major("600", Currency.USD))


class TestAPaymentRecordsMoneyThatMoved:
    def test_zero_settles_nothing(self):
        with pytest.raises(InvalidMoneyError):
            a_payment(amount=Money.zero(Currency.UZS))

    def test_a_negative_amount_must_name_what_it_reverses(self):
        with pytest.raises(InvalidMoneyError):
            a_payment(amount=som("-800000"))

    def test_a_reversal_gives_money_back(self):
        with pytest.raises(InvalidMoneyError):
            a_payment(amount=som("800000"), reverses_payment_id=uuid4())


class TestReversingCompensates:
    """FR-11.8: the original stays and a negative row is written beside it."""

    def test_the_compensating_row_is_the_negation(self):
        original = a_payment(amount=som("800000"))

        compensating = original.reversed(NOW, uuid4())

        assert compensating.amount == som("-800000")
        assert compensating.sales_invoice_id == original.sales_invoice_id

    def test_it_names_the_payment_it_reverses(self):
        original = a_payment()

        compensating = original.reversed(NOW, uuid4())

        assert compensating.reverses_payment_id == original.id
        assert compensating.is_reversal

    def test_it_names_whoever_reversed_it_not_whoever_took_the_money(self):
        collector, manager = uuid4(), uuid4()
        original = a_payment(user_id=collector)

        compensating = original.reversed(NOW, manager)

        assert compensating.user_id == manager

    def test_a_reversal_is_not_itself_reversed(self):
        """Reversing a reversal would re-apply the payment. A fresh payment
        is how money comes back in."""
        compensating = a_payment().reversed(NOW, uuid4())

        with pytest.raises(PaymentAlreadyReversedError):
            compensating.reversed(NOW, uuid4())
