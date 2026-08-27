"""The sales-side reports, read from the invoice and its lines.

A reporting path rather than more methods on ``SqlSalesInvoiceRepository``
(``.claude/rules/code-quality.md``): none of these loads an invoice, they
flatten joins across four tables into rows a report renders directly, and
keeping them here is what stops the aggregate's own repository growing a
second job.

No draft reaches any of them. A draft has resolved no price, opened no
debt and sold no handset, so it holds nothing these questions ask about —
and a draft's line reserves no price at all (FR-4.5b1).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Row, UnaryExpression, func, select
from sqlalchemy.orm import aliased

from application.dtos import DebtorSummary, PriceDeviation, UnitSale
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

from .base import TenantRepository


class SqlSalesReportRepository(TenantRepository):
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
            # Left: an accessory line names no handset, and it deviates as
            # readily as a phone does.
            .outerjoin(
                DeviceUnitModel,
                DeviceUnitModel.id == SalesInvoiceLineModel.device_unit_id,
            )
            # Left on both: a walk-in sale names no customer, and a line
            # whose deviation predates FR-4.5f's approver names nobody.
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
        # untouched line names no approver, and neither belongs at the top of
        # a list sorted by the column it is missing.
        leading: tuple[UnaryExpression[str], ...] = ()
        if sort is DeviationSort.APPROVER:
            leading = (approver.full_name.asc().nulls_last(),)
        elif sort is DeviationSort.CUSTOMER:
            leading = (CustomerModel.full_name.asc().nulls_last(),)
        stmt = stmt.order_by(
            *leading, SalesInvoiceModel.confirmed_at.desc(), SalesInvoiceLineModel.id
        )

        return await self._page_rows(stmt, page, page_size, self._to_deviation)

    async def sales_of_unit(self, device_unit_id: UUID) -> dict[UUID, UnitSale]:
        """Every confirmed line that sold this handset, keyed by invoice.

        Keyed rather than listed because the trace attaches each one to the
        ``SALE`` movement that names the same document, which is exact — a
        handset sold, cancelled and sold again produces two of each and no
        guessing about which price belongs to which sale.
        """
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
        sold = await self._many_rows(stmt, self._to_unit_sale)
        return {sale.invoice_id: sale for sale in sold}

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
        # Both come off outer joins; the two prices are null on a line whose
        # invoice never reached confirm.
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

    async def list_debtors(
        self, page: int, page_size: int
    ) -> tuple[list[DebtorSummary], int]:
        # A correlated subquery rather than a join, for the same reason
        # ``credit_history_for`` uses one: joining ``payments`` would repeat
        # an invoice once per payment and count its debt that many times.
        paid = (
            select(func.coalesce(func.sum(PaymentModel.amount_minor), 0))
            .where(PaymentModel.sales_invoice_id == SalesInvoiceModel.id)
            .scalar_subquery()
        )
        remaining = SalesInvoiceModel.debt_minor - paid
        # Grouped in SQL rather than in Python: a debtor list that loaded
        # every credit sale and every payment to add them up would read the
        # store's whole history to answer one question.
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
            # Settled sales drop out here rather than in a HAVING, so the
            # count and the age describe the open debts and nothing else.
            .where(
                SalesInvoiceModel.status == DocumentStatus.CONFIRMED.value,
                SalesInvoiceModel.payment_type == PaymentType.STORE_CREDIT.value,
                remaining > 0,
            )
            .group_by(CustomerModel.id, CustomerModel.full_name, CustomerModel.phone)
            # Oldest open invoice first. Store credit has no due date by
            # design (§4.7), so age is the only thing that makes a stale
            # debt visible; ``id`` breaks ties so a page boundary is stable.
            .order_by(func.min(SalesInvoiceModel.confirmed_at), CustomerModel.id)
        )
        return await self._page_rows(stmt, page, page_size, self._to_debtor)

    @staticmethod
    def _som(total: int | Decimal | None) -> Money:
        """All customer debt is som (§4.7), and Postgres widens a
        ``SUM(BIGINT)`` to ``NUMERIC`` — which ``Money`` refuses."""
        return Money(int(total or 0), Currency.UZS)

    @classmethod
    def _to_debtor(
        cls, row: Row[tuple[UUID, str, str | None, int, datetime | None, int]]
    ) -> DebtorSummary:
        customer_id, full_name, phone, balance, oldest, open_count = row._tuple()
        # Non-null by the query's own WHERE: it counts confirmed invoices
        # only, and a confirmed document carries its confirm timestamp.
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
    def _money(minor: int | None, currency: Currency) -> Money | None:
        return None if minor is None else Money(minor, currency)

    @staticmethod
    def _to_deviation(
        row: Row[tuple[SalesInvoiceModel, SalesInvoiceLineModel, str, str, str, str, str]],
    ) -> PriceDeviation:
        invoice, line, product_name, currency_code, scanned, customer, approver = (
            row._tuple()
        )
        # Nullable at runtime whatever the column type says — all three of
        # these come off outer joins.
        imei: str | None = scanned
        customer_name: str | None = customer
        approver_name: str | None = approver
        currency = Currency(currency_code)
        # Both are non-null by the query's own WHERE — a confirmed line has
        # snapshotted both prices (FR-4.5b).
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

