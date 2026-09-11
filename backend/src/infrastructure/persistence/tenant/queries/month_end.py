"""The reads only the month-end close needs (§5.10).

Split from ``SqlSalesInvoiceQueries`` rather than added to it: every method
here is a period question — what was owed at an instant, what moved in a
window — and the sales queries answer "now" questions about one customer or
one invoice. Both read ``sales_invoices``; they do not read it for the same
reason.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, select

from application.dtos import FinancingSplitRow, SettledSale, TradeInPayout
from domain.enums import (
    AcquisitionSource,
    DocumentType,
    PaymentType,
    TransactionType,
)
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    CreditCompanyModel,
    CustomerReturnModel,
    FinancialTransactionModel,
    GoodsReceiptLineModel,
    GoodsReceiptModel,
    PaymentModel,
    ProductModel,
    ReceivedUnitModel,
    SalesInvoiceModel,
)
from infrastructure.types import TenantSession

_I = SalesInvoiceModel
_F = FinancialTransactionModel
_R = CustomerReturnModel
_G = GoodsReceiptModel
_GL = GoodsReceiptLineModel
_U = ReceivedUnitModel


class SqlMonthEndQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def debt_at(self, as_of: datetime) -> Money:
        """``total_debt`` rewound to an instant (FR-10.7b).

        "Not cancelled *yet*" is the clause that makes a past month right: a
        sale cancelled in March was still owed at the end of January, and a
        plain status filter would quietly erase it from that month.
        """
        open_then = self._open_debt_at(as_of)
        owed = await self._session.scalar(
            select(func.coalesce(func.sum(_I.debt_minor), 0)).where(*open_then)
        )
        collected = await self._session.scalar(
            select(func.coalesce(func.sum(PaymentModel.amount_minor), 0))
            .join(_I, _I.id == PaymentModel.sales_invoice_id)
            .where(PaymentModel.occurred_at < as_of, *open_then)
        )
        # Rewound the same way: a return confirmed in March relieved
        # nothing that was owed at the end of January.
        relieved = await self._session.scalar(
            select(func.coalesce(func.sum(_R.debt_relief_minor), 0))
            .join(_I, _I.id == _R.sales_invoice_id)
            .where(_R.confirmed_at.is_not(None), _R.confirmed_at < as_of, *open_then)
        )
        return self._som(owed) - self._som(collected) - self._som(relieved)

    async def debt_booked_between(self, since: datetime, until: datetime) -> Money:
        booked = await self._session.scalar(
            select(func.coalesce(func.sum(_I.debt_minor), 0)).where(
                _I.payment_type == PaymentType.STORE_CREDIT.value,
                _I.confirmed_at >= since,
                _I.confirmed_at < until,
            )
        )
        return self._som(booked)

    async def debt_voided_between(self, since: datetime, until: datetime) -> Money:
        """What a cancellation took off the books (FR-11.11): the debt less
        everything ever collected against it.

        Payments already received are surfaced for refund handling, never
        deleted, so they stay in "cash collected" — voiding the gross debt
        would take them out of the movement twice.
        """
        cancelled = [
            _I.payment_type == PaymentType.STORE_CREDIT.value,
            _I.cancelled_at >= since,
            _I.cancelled_at < until,
        ]
        owed = await self._session.scalar(
            select(func.coalesce(func.sum(_I.debt_minor), 0)).where(*cancelled)
        )
        paid = await self._session.scalar(
            select(func.coalesce(func.sum(PaymentModel.amount_minor), 0))
            .join(_I, _I.id == PaymentModel.sales_invoice_id)
            .where(*cancelled)
        )
        # Relief taken before the cancellation left the books under its own
        # line; voiding the gross debt would remove it twice.
        relieved = await self._session.scalar(
            select(func.coalesce(func.sum(_R.debt_relief_minor), 0))
            .join(_I, _I.id == _R.sales_invoice_id)
            .where(_R.confirmed_at.is_not(None), *cancelled)
        )
        return self._som(owed) - self._som(paid) - self._som(relieved)

    async def debt_relieved_between(self, since: datetime, until: datetime) -> Money:
        """What customer returns wrote off the books in the window (FR-4.9d).

        Scoped to returns *confirmed* in the window and to sales still
        standing at the end of it: a cancelled sale's whole remaining debt
        goes out through ``debt_voided_between`` instead, and counting the
        relief here as well would take it off twice.
        """
        relieved = await self._session.scalar(
            select(func.coalesce(func.sum(_R.debt_relief_minor), 0))
            .join(_I, _I.id == _R.sales_invoice_id)
            .where(
                _I.payment_type == PaymentType.STORE_CREDIT.value,
                _R.confirmed_at >= since,
                _R.confirmed_at < until,
                (_I.cancelled_at.is_(None)) | (_I.cancelled_at >= until),
            )
        )
        return self._som(relieved)

    async def sales_by_financing(
        self,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[FinancingSplitRow]:
        """Revenue comes off the ``SALE_REVENUE`` rows, not the invoice
        lines, so the split adds back up to the report's own revenue figure.

        A mixed-currency invoice (§4.5) is counted in each currency it
        billed in; the alternative is a count belonging to no column.
        """
        stmt = (
            select(
                _I.payment_type,
                _I.credit_company_id,
                CreditCompanyModel.name,
                _F.currency,
                func.count(func.distinct(_I.id)),
                func.sum(_F.amount_minor),
            )
            .join(_I, _I.id == _F.document_id)
            .outerjoin(CreditCompanyModel, CreditCompanyModel.id == _I.credit_company_id)
            .where(
                _F.txn_type == TransactionType.SALE_REVENUE.value,
                _F.document_type == DocumentType.SALES_INVOICE.value,
                _F.occurred_at >= since,
                _F.occurred_at < until,
            )
            .group_by(_I.payment_type, _I.credit_company_id, CreditCompanyModel.name, _F.currency)
            .order_by(_I.payment_type, CreditCompanyModel.name)
        )
        if location_id is not None:
            stmt = stmt.where(_F.location_id == location_id)
        rows = await self._session.execute(stmt)
        return [
            FinancingSplitRow(
                payment_type=PaymentType(payment_type),
                credit_company_id=company_id,
                credit_company_name=company_name,
                invoice_count=int(count or 0),
                revenue=Money(int(revenue or 0), Currency(currency)),
            )
            for payment_type, company_id, company_name, currency, count, revenue in rows
        ]

    async def settled_sales(
        self,
        *,
        timezone: str,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[SettledSale]:
        """What each sale confirmed in the window charged, and what settled it.

        Charged comes off the ``SALE_REVENUE`` rows rather than the lines, so
        it adds back up to the report's own revenue figure. Settled is the
        tender rows on a sale settled at the counter (a reversal is a
        negative one, so the sum nets), and on a store-credit sale the debt
        agreed instead: a payment against that debt is the same money
        arriving, and counting both would state it twice.
        """
        day = cast(func.timezone(timezone, _I.confirmed_at), Date).label("day")
        charged = (
            select(_I.id, day, _F.currency, func.sum(_F.amount_minor))
            .join(_F, _F.document_id == _I.id)
            .where(
                _F.txn_type == TransactionType.SALE_REVENUE.value,
                _F.document_type == DocumentType.SALES_INVOICE.value,
                _I.confirmed_at >= since,
                _I.confirmed_at < until,
                _I.cancelled_at.is_(None),
            )
            .group_by(_I.id, day, _F.currency)
        )
        if location_id is not None:
            charged = charged.where(_I.location_id == location_id)

        days: dict[UUID, date] = {}
        billed: dict[UUID, list[Money]] = {}
        for invoice_id, on, currency, total in await self._session.execute(charged):
            days[invoice_id] = on
            billed.setdefault(invoice_id, []).append(
                Money(int(total or 0), Currency(currency))
            )
        if not days:
            return []

        on_credit: dict[UUID, Money] = {}
        owed = select(_I.id, _I.debt_minor).where(
            _I.id.in_(days),
            _I.payment_type == PaymentType.STORE_CREDIT.value,
            _I.debt_minor.is_not(None),
        )
        for invoice_id, debt in await self._session.execute(owed):
            on_credit[invoice_id] = Money(int(debt), Currency.UZS)

        tendered: dict[UUID, list[Money]] = {}
        paid = (
            select(
                PaymentModel.sales_invoice_id,
                PaymentModel.currency,
                func.sum(PaymentModel.amount_minor),
            )
            .where(PaymentModel.sales_invoice_id.in_(set(days) - set(on_credit)))
            .group_by(PaymentModel.sales_invoice_id, PaymentModel.currency)
        )
        for invoice_id, currency, total in await self._session.execute(paid):
            amount = Money(int(total or 0), Currency(currency))
            if not amount.is_zero:
                tendered.setdefault(invoice_id, []).append(amount)

        return [
            SettledSale(
                day=days[invoice_id],
                charged=tuple(amounts),
                received=(on_credit[invoice_id],)
                if invoice_id in on_credit
                else tuple(tendered.get(invoice_id, ())),
                on_credit=invoice_id in on_credit,
            )
            for invoice_id, amounts in billed.items()
        ]

    async def trade_in_payouts(
        self,
        *,
        timezone: str,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[TradeInPayout]:
        """One handset bought off a walk-in in the window: valued, and paid for."""
        day = cast(func.timezone(timezone, _G.confirmed_at), Date).label("day")
        stmt = (
            select(
                _G.id,
                day,
                ProductModel.currency,
                func.sum(_U.acquisition_cost_minor),
                _U.cash_paid_currency,
                func.sum(_U.cash_paid_minor),
            )
            .join(_GL, _GL.goods_receipt_id == _G.id)
            .join(_U, _U.goods_receipt_line_id == _GL.id)
            .join(ProductModel, ProductModel.id == _GL.product_id)
            .where(
                _G.acquisition_source == AcquisitionSource.TRADE_IN.value,
                _G.confirmed_at >= since,
                _G.confirmed_at < until,
                _G.cancelled_at.is_(None),
            )
            .group_by(_G.id, day, ProductModel.currency, _U.cash_paid_currency)
        )
        if location_id is not None:
            stmt = stmt.where(_G.location_id == location_id)

        days: dict[UUID, date] = {}
        valued: dict[UUID, list[Money]] = {}
        paid: dict[UUID, list[Money]] = {}
        for receipt_id, on, currency, cost, cash_currency, cash in (
            await self._session.execute(stmt)
        ):
            days[receipt_id] = on
            if cost is not None:
                valued.setdefault(receipt_id, []).append(
                    Money(int(cost), Currency(currency))
                )
            if cash is not None and cash_currency is not None:
                paid.setdefault(receipt_id, []).append(
                    Money(int(cash), Currency(cash_currency))
                )
        return [
            TradeInPayout(
                day=on,
                valued=tuple(valued.get(receipt_id, ())),
                paid=tuple(paid.get(receipt_id, ())),
            )
            for receipt_id, on in days.items()
        ]

    @staticmethod
    def _open_debt_at(as_of: datetime) -> list[Any]:
        """A store-credit sale confirmed before *as_of* and not cancelled by it."""
        return [
            _I.payment_type == PaymentType.STORE_CREDIT.value,
            _I.confirmed_at < as_of,
            (_I.cancelled_at.is_(None)) | (_I.cancelled_at >= as_of),
        ]

    @staticmethod
    def _som(total: int | Decimal | None) -> Money:
        """Postgres widens ``SUM(BIGINT)`` to ``NUMERIC``, which ``Money``
        refuses. Every summand was a whole som, so this is lossless."""
        return Money(int(total or 0), Currency.UZS)
