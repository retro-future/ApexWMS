"""Sales-side reads that are not "load a whole invoice".

The account and debtor totals and the deviation report flatten joins across
four tables into rows a report renders directly, which a ``Specification``
cannot express (ADR 0007). Split off ``SqlSalesInvoiceRepository`` and
``SqlSalesReportRepository`` when the aggregate moved to the generic
repository. Same shape as ``SqlGoodsReceiptQueries``.

No draft reaches any of them: a draft has resolved no price, opened no debt
and sold no handset (FR-4.5b1).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, Select, UnaryExpression, func, select
from sqlalchemy.orm import aliased

from application.dtos import (
    CreditInvoiceDebt,
    DebtorSummary,
    PriceDeviation,
    UnitSale,
)
from application.sorting import DeviationSort
from domain.enums import DocumentStatus, PaymentType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    CustomerModel,
    DeviceUnitModel,
    EmployeeModel,
    PaymentModel,
    ProductModel,
    SalesInvoiceLineModel,
    SalesInvoiceModel,
)
from infrastructure.types import TenantSession


class SqlSalesInvoiceQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def credit_history_for(self, customer_id: UUID) -> list[CreditInvoiceDebt]:
        # A correlated subquery rather than a join, so an invoice with three
        # payments still comes back as one row.
        paid = (
            select(func.coalesce(func.sum(PaymentModel.amount_minor), 0))
            .where(PaymentModel.sales_invoice_id == SalesInvoiceModel.id)
            .scalar_subquery()
        )
        stmt = (
            select(SalesInvoiceModel, paid)
            .where(
                SalesInvoiceModel.customer_id == customer_id,
                SalesInvoiceModel.payment_type != PaymentType.PAID_IN_FULL.value,
                SalesInvoiceModel.status != DocumentStatus.DRAFT.value,
            )
            .order_by(SalesInvoiceModel.confirmed_at.desc(), SalesInvoiceModel.id)
        )
        rows = await self._session.execute(stmt)
        return [self._to_credit_debt(row) for row in rows]

    async def total_debt(self) -> Money:
        owed = await self._session.scalar(
            select(func.coalesce(func.sum(SalesInvoiceModel.debt_minor), 0)).where(
                SalesInvoiceModel.status == DocumentStatus.CONFIRMED.value,
                SalesInvoiceModel.payment_type == PaymentType.STORE_CREDIT.value,
            )
        )
        collected = await self._session.scalar(
            select(func.coalesce(func.sum(PaymentModel.amount_minor), 0))
            .join(
                SalesInvoiceModel, SalesInvoiceModel.id == PaymentModel.sales_invoice_id
            )
            .where(SalesInvoiceModel.status == DocumentStatus.CONFIRMED.value)
        )
        return self._som(owed) - self._som(collected)

    async def list_deviations(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        approved_by: UUID | None = None,
        customer_id: UUID | None = None,
        sort: DeviationSort = DeviationSort.CONFIRMED_AT,
    ) -> tuple[list[PriceDeviation], int]:
        approver = aliased(EmployeeModel)
        stmt = (
            select(
                SalesInvoiceModel,
                SalesInvoiceLineModel,
                ProductModel.name,
                ProductModel.currency,
                DeviceUnitModel.imei,
                CustomerModel.full_name,
                approver.full_name,
            )
            .join(
                SalesInvoiceModel,
                SalesInvoiceModel.id == SalesInvoiceLineModel.sales_invoice_id,
            )
            .join(ProductModel, ProductModel.id == SalesInvoiceLineModel.product_id)
            .outerjoin(
                DeviceUnitModel,
                DeviceUnitModel.id == SalesInvoiceLineModel.device_unit_id,
            )
            .outerjoin(CustomerModel, CustomerModel.id == SalesInvoiceModel.customer_id)
            .outerjoin(approver, approver.id == SalesInvoiceLineModel.price_approved_by)
            .where(
                SalesInvoiceModel.status == DocumentStatus.CONFIRMED.value,
                SalesInvoiceLineModel.resolved_price_minor.is_not(None),
                SalesInvoiceLineModel.charged_price_minor.is_not(None),
                SalesInvoiceLineModel.charged_price_minor
                != SalesInvoiceLineModel.resolved_price_minor,
            )
        )
        if from_date is not None:
            stmt = stmt.where(SalesInvoiceModel.confirmed_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(SalesInvoiceModel.confirmed_at <= to_date)
        if approved_by is not None:
            stmt = stmt.where(SalesInvoiceLineModel.price_approved_by == approved_by)
        if customer_id is not None:
            stmt = stmt.where(SalesInvoiceModel.customer_id == customer_id)

        # Nulls last either way: an accessory line names no customer and an
        # untouched line names no approver.
        leading: tuple[UnaryExpression[str], ...] = ()
        if sort is DeviationSort.APPROVER:
            leading = (approver.full_name.asc().nulls_last(),)
        elif sort is DeviationSort.CUSTOMER:
            leading = (CustomerModel.full_name.asc().nulls_last(),)
        stmt = stmt.order_by(
            *leading, SalesInvoiceModel.confirmed_at.desc(), SalesInvoiceLineModel.id
        )

        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_deviation(row) for row in rows], total

    async def sales_of_unit(self, device_unit_id: UUID) -> dict[UUID, UnitSale]:
        """Every non-draft line that sold this handset, keyed by invoice."""
        approver = aliased(EmployeeModel)
        stmt = (
            select(
                SalesInvoiceModel.id,
                SalesInvoiceModel.number,
                SalesInvoiceModel.customer_id,
                CustomerModel.full_name,
                SalesInvoiceLineModel.resolved_price_minor,
                SalesInvoiceLineModel.charged_price_minor,
                SalesInvoiceLineModel.price_approved_by,
                approver.full_name,
                SalesInvoiceLineModel.price_note,
                ProductModel.currency,
            )
            .join(
                SalesInvoiceModel,
                SalesInvoiceModel.id == SalesInvoiceLineModel.sales_invoice_id,
            )
            .join(ProductModel, ProductModel.id == SalesInvoiceLineModel.product_id)
            .outerjoin(CustomerModel, CustomerModel.id == SalesInvoiceModel.customer_id)
            .outerjoin(approver, approver.id == SalesInvoiceLineModel.price_approved_by)
            .where(
                SalesInvoiceLineModel.device_unit_id == device_unit_id,
                SalesInvoiceModel.status != DocumentStatus.DRAFT.value,
            )
        )
        rows = await self._session.execute(stmt)
        sold = [self._to_unit_sale(row) for row in rows]
        return {sale.invoice_id: sale for sale in sold}

    async def list_debtors(
        self, page: int, page_size: int
    ) -> tuple[list[DebtorSummary], int]:
        paid = (
            select(func.coalesce(func.sum(PaymentModel.amount_minor), 0))
            .where(PaymentModel.sales_invoice_id == SalesInvoiceModel.id)
            .scalar_subquery()
        )
        remaining = SalesInvoiceModel.debt_minor - paid
        stmt = (
            select(
                CustomerModel.id,
                CustomerModel.full_name,
                CustomerModel.phone,
                func.sum(remaining),
                func.min(SalesInvoiceModel.confirmed_at),
                func.count(SalesInvoiceModel.id),
            )
            .join(CustomerModel, CustomerModel.id == SalesInvoiceModel.customer_id)
            .where(
                SalesInvoiceModel.status == DocumentStatus.CONFIRMED.value,
                SalesInvoiceModel.payment_type == PaymentType.STORE_CREDIT.value,
                remaining > 0,
            )
            .group_by(CustomerModel.id, CustomerModel.full_name, CustomerModel.phone)
            .order_by(func.min(SalesInvoiceModel.confirmed_at), CustomerModel.id)
        )
        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_debtor(row) for row in rows], total

    async def _count(self, stmt: Select[Any]) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        return total or 0

    @staticmethod
    def _minor(amount: Money | None) -> int | None:
        return None if amount is None else amount.amount_minor

    @staticmethod
    def _som(total: int | Decimal | None) -> Money:
        """Postgres widens ``SUM(BIGINT)`` to ``NUMERIC`` and asyncpg returns
        a ``Decimal``, which ``Money`` refuses. Every summand was a whole
        som, so the conversion is lossless."""
        return Money(int(total or 0), Currency.UZS)

    @staticmethod
    def _money(minor: int | None, currency: Currency) -> Money | None:
        return Money(minor, currency) if minor is not None else None

    @classmethod
    def _to_credit_debt(
        cls, row: Row[tuple[SalesInvoiceModel, int]]
    ) -> CreditInvoiceDebt:
        invoice, paid = row._tuple()
        return CreditInvoiceDebt(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            status=DocumentStatus(invoice.status),
            payment_type=PaymentType(invoice.payment_type),
            confirmed_at=invoice.confirmed_at,
            debt=cls._money(invoice.debt_minor, Currency.UZS),
            paid=cls._som(paid),
            credit_company_id=invoice.credit_company_id,
            contract_ref=invoice.contract_ref,
        )

    @staticmethod
    def _to_unit_sale(
        row: Row[
            tuple[
                UUID,
                str,
                UUID | None,
                str,
                int | None,
                int | None,
                UUID | None,
                str,
                str | None,
                str,
            ]
        ],
    ) -> UnitSale:
        (
            invoice_id,
            number,
            customer_id,
            customer,
            resolved,
            charged,
            approved_by,
            approver,
            price_note,
            currency_code,
        ) = row._tuple()
        currency = Currency(currency_code)
        customer_name: str | None = customer
        approver_name: str | None = approver
        return UnitSale(
            invoice_id=invoice_id,
            invoice_number=number,
            customer_id=customer_id,
            customer_name=customer_name,
            resolved_price=Money(resolved, currency) if resolved is not None else None,
            charged_price=Money(charged, currency) if charged is not None else None,
            price_approved_by=approved_by,
            price_approved_by_name=approver_name,
            price_note=price_note,
        )

    @classmethod
    def _to_debtor(
        cls, row: Row[tuple[UUID, str, str | None, int, datetime | None, int]]
    ) -> DebtorSummary:
        customer_id, full_name, phone, balance, oldest, open_count = row._tuple()
        assert oldest is not None
        return DebtorSummary(
            customer_id=customer_id,
            full_name=full_name,
            phone=phone,
            balance=cls._som(balance),
            oldest_open_at=oldest,
            open_invoice_count=open_count,
        )

    @staticmethod
    def _to_deviation(
        row: Row[tuple[SalesInvoiceModel, SalesInvoiceLineModel, str, str, str, str, str]],
    ) -> PriceDeviation:
        invoice, line, product_name, currency_code, scanned, customer, approver = (
            row._tuple()
        )
        imei: str | None = scanned
        customer_name: str | None = customer
        approver_name: str | None = approver
        currency = Currency(currency_code)
        assert line.resolved_price_minor is not None
        assert line.charged_price_minor is not None
        assert invoice.confirmed_at is not None
        return PriceDeviation(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            confirmed_at=invoice.confirmed_at,
            customer_id=invoice.customer_id,
            customer_name=customer_name,
            product_id=line.product_id,
            product_name=product_name,
            imei=imei,
            resolved_price=Money(line.resolved_price_minor, currency),
            charged_price=Money(line.charged_price_minor, currency),
            price_approved_by=line.price_approved_by,
            price_approved_by_name=approver_name,
            price_note=line.price_note,
        )
