"""What one customer owes, and what they were sold on credit (FR-11.9).

Two lists, deliberately separate. ``openDebts`` is money the store is
waiting for; ``financedSales`` is money it has already been paid by a
credit company, shown only so the customer's history is complete. Merging
them into one table would put a zero-balance sale next to a real debt and
invite the reader to add them up — and attributing a company's debt to the
customer is the most misleading thing this system could do (PRD §4.7).

Every figure is som and the balance is a single number, because that is
what all customer debt is (§4.7). There are no per-currency balances here
and no place to put one.

``daysSinceSale`` is computed against the request's clock rather than
stored: store credit has no due date by design, so age is the only thing
that makes a stale debt visible.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import CreditInvoiceDebt
from application.models.money import MoneyData
from domain.entities import Customer
from domain.enums import DocumentStatus, PaymentType
from domain.value_objects import Currency, Money


class CreditInvoiceDebtData(CamelModel):
    invoice_id: UUID
    invoice_number: str
    status: DocumentStatus
    payment_type: PaymentType
    confirmed_at: datetime | None
    debt: MoneyData | None
    paid: MoneyData
    remaining: MoneyData
    credit_company_id: UUID | None
    contract_ref: str | None
    days_since_sale: int | None

    @classmethod
    def from_entity(cls, debt: CreditInvoiceDebt, now: datetime) -> CreditInvoiceDebtData:
        age = None if debt.confirmed_at is None else (now - debt.confirmed_at).days
        return cls(
            invoice_id=debt.invoice_id,
            invoice_number=debt.invoice_number,
            status=debt.status,
            payment_type=debt.payment_type,
            confirmed_at=debt.confirmed_at,
            debt=MoneyData.from_entity(debt.debt),
            paid=MoneyData.from_entity(debt.paid),
            remaining=MoneyData.from_entity(debt.remaining),
            credit_company_id=debt.credit_company_id,
            contract_ref=debt.contract_ref,
            days_since_sale=age,
        )


class CustomerAccountData(CamelModel):
    customer_id: UUID
    full_name: str
    phone: str | None
    balance: MoneyData
    open_debts: list[CreditInvoiceDebtData]
    financed_sales: list[CreditInvoiceDebtData]

    @classmethod
    def from_entity(
        cls, customer: Customer, history: list[CreditInvoiceDebt], now: datetime
    ) -> CustomerAccountData:
        balance = Money.zero(Currency.UZS)
        for entry in history:
            balance = balance + entry.remaining
        return cls(
            customer_id=customer.id,
            full_name=customer.full_name,
            phone=customer.phone,
            balance=MoneyData.from_entity(balance),
            open_debts=[
                CreditInvoiceDebtData.from_entity(entry, now)
                for entry in history
                if entry.payment_type is PaymentType.STORE_CREDIT
            ],
            financed_sales=[
                CreditInvoiceDebtData.from_entity(entry, now)
                for entry in history
                if entry.payment_type is PaymentType.CREDIT_COMPANY
            ],
        )
