"""Sales invoices and their lines, as one aggregate (PRD §4.4, §5.4).

Every read joins ``products``, for the same reason the two inbound document
repositories do: a line's three money columns are bare minor amounts
denominated by the catalog row (§4.5 rule 3), and its tracking type is the
product's. The line is rebuilt from a ``Row``, which is why this is a
``TenantRepository`` and not a ``TenantCrudRepository``.

``add_line``/``update_line``/``remove_line`` exist because a scan is one
row: rewriting the whole invoice per beep would put the document through
the database on every trigger pull, and §6 gives the round trip 200ms.

``update`` writes the header and, unlike the inbound documents, every
line's snapshot — confirming an invoice is the one moment its lines change
in bulk, since ``resolved_price``/``charged_price`` are written for all of
them at once (FR-4.5b1).
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Row, delete, func, or_, select

from application.dtos import CreditInvoiceDebt, DebtorSummary, PriceDeviation
from domain.entities import SalesInvoice, SalesInvoiceLine
from domain.enums import DocumentStatus, PaymentType, TrackingType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    CustomerModel,
    DeviceUnitModel,
    PaymentModel,
    ProductModel,
    SalesInvoiceLineModel,
    SalesInvoiceModel,
)

from .base import TenantRepository


class SqlSalesInvoiceRepository(TenantRepository):
    async def get(self, key: UUID) -> SalesInvoice | None:
        row = await self._row(SalesInvoiceModel, key)
        if row is None:
            return None
        lines = await self._lines_for([key])
        return self._to_entity(row, lines[key])

    async def add(self, entity: SalesInvoice) -> None:
        await self._insert(self._to_model(entity))
        for line in entity.lines:
            await self.add_line(line)

    async def update(self, entity: SalesInvoice) -> None:
        row = await self._require_row(SalesInvoiceModel, entity.id)
        # The number, the author and the location are absent on purpose:
        # none of them can change about an invoice once it is open.
        row.status = entity.status.value
        row.customer_id = entity.customer_id
        row.note = entity.note
        row.payment_type = entity.payment_type.value
        row.credit_company_id = entity.credit_company_id
        row.contract_ref = entity.contract_ref
        row.debt_minor = self._minor(entity.debt)
        row.confirmed_by = entity.confirmed_by
        row.confirmed_at = entity.confirmed_at
        row.cancelled_by = entity.cancelled_by
        row.cancelled_at = entity.cancelled_at
        row.cancellation_reason = entity.cancellation_reason
        for line in entity.lines:
            await self.update_line(line)

    async def add_line(self, line: SalesInvoiceLine) -> None:
        await self._insert(
            SalesInvoiceLineModel(
                id=line.id,
                sales_invoice_id=line.sales_invoice_id,
                product_id=line.product_id,
                device_unit_id=line.device_unit_id,
                quantity=line.quantity,
                override_price_minor=self._minor(line.override_price),
                price_approved_by=line.price_approved_by,
                price_note=line.price_note,
                resolved_price_minor=self._minor(line.resolved_price),
                charged_price_minor=self._minor(line.charged_price),
            )
        )

    async def update_line(self, line: SalesInvoiceLine) -> None:
        row = await self._require_row(SalesInvoiceLineModel, line.id)
        # The product and the handset are absent on purpose: a line naming
        # the wrong phone is removed and re-scanned, so the operator sees
        # the sellability checks run against the new one.
        row.quantity = line.quantity
        row.override_price_minor = self._minor(line.override_price)
        row.price_approved_by = line.price_approved_by
        row.price_note = line.price_note
        row.resolved_price_minor = self._minor(line.resolved_price)
        row.charged_price_minor = self._minor(line.charged_price)

    async def remove_line(self, line_id: UUID) -> None:
        await self._session.execute(
            delete(SalesInvoiceLineModel).where(SalesInvoiceLineModel.id == line_id)
        )

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        customer_id: UUID | None = None,
        location_id: UUID | None = None,
    ) -> tuple[list[SalesInvoice], int]:
        stmt = select(SalesInvoiceModel)
        if search:
            # One box, three ways a seller actually looks a sale up: the
            # invoice number, the customer's name or phone, or a handset's
            # IMEI. The IMEI check is a correlated EXISTS rather than a join
            # so a two-line invoice cannot come back twice.
            term = f"%{search.strip()}%"
            imei_match = (
                select(SalesInvoiceLineModel.id)
                .join(
                    DeviceUnitModel,
                    DeviceUnitModel.id == SalesInvoiceLineModel.device_unit_id,
                )
                .where(
                    SalesInvoiceLineModel.sales_invoice_id == SalesInvoiceModel.id,
                    DeviceUnitModel.imei.ilike(term),
                )
                .exists()
            )
            stmt = stmt.outerjoin(
                CustomerModel, CustomerModel.id == SalesInvoiceModel.customer_id
            ).where(
                or_(
                    SalesInvoiceModel.number.ilike(term),
                    CustomerModel.full_name.ilike(term),
                    CustomerModel.phone.ilike(term),
                    imei_match,
                )
            )
        if status is not None:
            stmt = stmt.where(SalesInvoiceModel.status == status.value)
        if customer_id is not None:
            stmt = stmt.where(SalesInvoiceModel.customer_id == customer_id)
        if location_id is not None:
            stmt = stmt.where(SalesInvoiceModel.location_id == location_id)
        # Newest first: the counter reads the top of the list, and ``id``
        # breaks ties so a page boundary is stable.
        stmt = stmt.order_by(SalesInvoiceModel.created_at.desc(), SalesInvoiceModel.id)

        rows, total = await self._page(stmt, page, page_size, lambda row: row)
        lines = await self._lines_for([row.id for row in rows])
        return [self._to_entity(row, lines[row.id]) for row in rows], total

    async def list_deviations(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        approved_by: UUID | None = None,
        customer_id: UUID | None = None,
    ) -> tuple[list[PriceDeviation], int]:
        stmt = (
            select(
                SalesInvoiceModel,
                SalesInvoiceLineModel,
                ProductModel.name,
                ProductModel.currency,
                DeviceUnitModel.imei,
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
        stmt = stmt.order_by(
            SalesInvoiceModel.confirmed_at.desc(), SalesInvoiceLineModel.id
        )

        return await self._page_rows(stmt, page, page_size, self._to_deviation)

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
        return await self._many_rows(stmt, self._to_credit_debt)

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

    async def _lines_for(
        self, invoice_ids: list[UUID]
    ) -> defaultdict[UUID, list[SalesInvoiceLine]]:
        lines: defaultdict[UUID, list[SalesInvoiceLine]] = defaultdict(list)
        if not invoice_ids:
            return lines

        stmt = (
            select(SalesInvoiceLineModel, ProductModel.currency, ProductModel.tracking_type)
            .join(ProductModel, ProductModel.id == SalesInvoiceLineModel.product_id)
            .where(SalesInvoiceLineModel.sales_invoice_id.in_(invoice_ids))
            # Scan order is what the counter saw, and it is the only order
            # that means anything on an invoice.
            .order_by(SalesInvoiceLineModel.id)
        )
        for row in await self._session.execute(stmt):
            line = self._to_line(row)
            lines[line.sales_invoice_id].append(line)
        return lines

    @staticmethod
    def _minor(amount: Money | None) -> int | None:
        return None if amount is None else amount.amount_minor

    @staticmethod
    def _som(total: int | Decimal | None) -> Money:
        """A summed som amount, as ``Money``.

        Postgres widens ``SUM(BIGINT)`` to ``NUMERIC`` and asyncpg returns
        a ``Decimal``, which ``Money`` refuses. Every summand was a whole
        som, so the conversion is lossless.
        """
        return Money(int(total or 0), Currency.UZS)

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
        row: Row[tuple[SalesInvoiceModel, SalesInvoiceLineModel, str, str, str]],
    ) -> PriceDeviation:
        invoice, line, product_name, currency_code, scanned = row._tuple()
        # Nullable at runtime whatever the column type says — the join onto
        # ``device_units`` is outer, because an accessory line names no
        # handset and deviates as readily as a phone does.
        imei: str | None = scanned
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
            product_id=line.product_id,
            product_name=product_name,
            imei=imei,
            resolved_price=Money(line.resolved_price_minor, currency),
            charged_price=Money(line.charged_price_minor, currency),
            price_approved_by=line.price_approved_by,
            price_note=line.price_note,
        )

    @classmethod
    def _to_line(cls, row: Row[tuple[SalesInvoiceLineModel, str, str]]) -> SalesInvoiceLine:
        model, currency_code, tracking_type = row._tuple()
        currency = Currency(currency_code)
        return SalesInvoiceLine(
            id=model.id,
            sales_invoice_id=model.sales_invoice_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            quantity=model.quantity,
            currency=currency,
            tracking_type=TrackingType(tracking_type),
            override_price=cls._money(model.override_price_minor, currency),
            price_approved_by=model.price_approved_by,
            price_note=model.price_note,
            resolved_price=cls._money(model.resolved_price_minor, currency),
            charged_price=cls._money(model.charged_price_minor, currency),
        )

    @staticmethod
    def _to_model(entity: SalesInvoice) -> SalesInvoiceModel:
        return SalesInvoiceModel(
            id=entity.id,
            number=entity.number,
            status=entity.status.value,
            location_id=entity.location_id,
            customer_id=entity.customer_id,
            note=entity.note,
            payment_type=entity.payment_type.value,
            credit_company_id=entity.credit_company_id,
            contract_ref=entity.contract_ref,
            debt_minor=None if entity.debt is None else entity.debt.amount_minor,
            created_by=entity.created_by,
            created_at=entity.created_at,
            confirmed_by=entity.confirmed_by,
            confirmed_at=entity.confirmed_at,
            cancelled_by=entity.cancelled_by,
            cancelled_at=entity.cancelled_at,
            cancellation_reason=entity.cancellation_reason,
        )

    @classmethod
    def _to_entity(
        cls, row: SalesInvoiceModel, lines: list[SalesInvoiceLine]
    ) -> SalesInvoice:
        return SalesInvoice(
            id=row.id,
            number=row.number,
            status=DocumentStatus(row.status),
            location_id=row.location_id,
            customer_id=row.customer_id,
            note=row.note,
            payment_type=PaymentType(row.payment_type),
            credit_company_id=row.credit_company_id,
            contract_ref=row.contract_ref,
            debt=cls._money(row.debt_minor, Currency.UZS),
            created_by=row.created_by,
            created_at=row.created_at,
            confirmed_by=row.confirmed_by,
            confirmed_at=row.confirmed_at,
            cancelled_by=row.cancelled_by,
            cancelled_at=row.cancelled_at,
            cancellation_reason=row.cancellation_reason,
            lines=lines,
        )
