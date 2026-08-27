"""The money ledger (PRD §4.6).

The one tenant table that stores its own currency, because a transaction
need not belong to a product: a ``PAYMENT_RECEIVED`` entry is som against
an invoice whose lines may be dollars (§4.7). So no join, and every
aggregate here **groups by currency** — a ``SUM`` that forgot to would add
cents to som.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, func, select

from application.dtos import FinancialLedgerRow, LedgerActor, SalesTotalsRow
from domain.entities import FinancialTransaction
from domain.enums import DocumentType, TransactionType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    EmployeeModel,
    FinancialTransactionModel,
    LocationModel,
    ProductModel,
)

from .base import TenantRepository
from .document_ref import document_number


class SqlFinancialTransactionRepository(TenantRepository):
    """Append and read. No ``update``: a cancellation books the negated
    entry (§4.3 rule 3), it does not edit the original."""

    def _to_model(self, entity: FinancialTransaction) -> FinancialTransactionModel:
        return FinancialTransactionModel(
            id=entity.id,
            occurred_at=entity.occurred_at,
            txn_type=entity.txn_type.value,
            amount_minor=entity.amount.amount_minor,
            currency=entity.amount.currency.value,
            document_type=entity.document_type.value,
            document_id=entity.document_id,
            location_id=entity.location_id,
            product_id=entity.product_id,
            device_unit_id=entity.device_unit_id,
            user_id=entity.user_id,
            note=entity.note,
        )

    def _to_entity(self, row: FinancialTransactionModel) -> FinancialTransaction:
        return FinancialTransaction(
            id=row.id,
            occurred_at=row.occurred_at,
            txn_type=TransactionType(row.txn_type),
            amount=Money(row.amount_minor, Currency(row.currency)),
            document_type=DocumentType(row.document_type),
            document_id=row.document_id,
            location_id=row.location_id,
            product_id=row.product_id,
            device_unit_id=row.device_unit_id,
            user_id=row.user_id,
            note=row.note,
        )

    async def add(self, entity: FinancialTransaction) -> None:
        await self._insert(self._to_model(entity))

    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[FinancialTransaction]:
        """Everything one document booked — what a cancellation reverses."""
        return await self._many(
            select(FinancialTransactionModel)
            .where(
                FinancialTransactionModel.document_type == document_type.value,
                FinancialTransactionModel.document_id == document_id,
            )
            .order_by(FinancialTransactionModel.occurred_at, FinancialTransactionModel.id),
            self._to_entity,
        )

    async def list_for_pair(
        self, product_id: UUID, location_id: UUID
    ) -> list[FinancialTransaction]:
        """What one product cost at one location, in order."""
        return await self._many(
            select(FinancialTransactionModel)
            .where(
                FinancialTransactionModel.product_id == product_id,
                FinancialTransactionModel.location_id == location_id,
                FinancialTransactionModel.device_unit_id.is_(None),
            )
            .order_by(FinancialTransactionModel.occurred_at, FinancialTransactionModel.id),
            self._to_entity,
        )

    async def totals_by_type(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency], Money]:
        """Every category's net, **per currency** — the month-end shape.

        Keyed by the pair on purpose: there is no total that spans both
        currencies, and a dict keyed on category alone would have nowhere
        to put the second one. *until* is exclusive, so a period is
        ``[start, next start)`` and no transaction lands in two months
        (FR-10.8).
        """
        stmt = select(
            FinancialTransactionModel.txn_type,
            FinancialTransactionModel.currency,
            func.sum(FinancialTransactionModel.amount_minor),
        ).group_by(FinancialTransactionModel.txn_type, FinancialTransactionModel.currency)
        if since is not None:
            stmt = stmt.where(FinancialTransactionModel.occurred_at >= since)
        if until is not None:
            stmt = stmt.where(FinancialTransactionModel.occurred_at < until)
        if location_id is not None:
            stmt = stmt.where(FinancialTransactionModel.location_id == location_id)

        rows = await self._session.execute(stmt)
        # ``int(...)`` is not defensive padding: Postgres widens
        # ``SUM(BIGINT)`` to ``NUMERIC``, which asyncpg hands back as a
        # ``Decimal`` — and ``Money`` refuses anything that is not an exact
        # ``int`` (§4.5). The conversion is lossless because every summand
        # was a whole minor unit; it is the driver's type, not the value,
        # that needs correcting.
        return {
            (TransactionType(txn_type), Currency(currency)): Money(
                int(total or 0), Currency(currency)
            )
            for txn_type, currency, total in rows
        }

    async def list_page(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        txn_type: TransactionType | None = None,
        location_id: UUID | None = None,
        document_type: DocumentType | None = None,
    ) -> tuple[list[FinancialLedgerRow], int]:
        """FR-10.3: the raw money ledger, newest first, mirroring FR-9.5.

        A log, not an aggregate. It carries no total on purpose: these rows
        mix currencies by design, and there is no figure that could sum a
        som payment and a dollar sale honestly (§4.5 rule 4).
        """
        number = document_number(
            FinancialTransactionModel.document_type,
            FinancialTransactionModel.document_id,
        )
        stmt = (
            select(
                FinancialTransactionModel,
                ProductModel.name,
                DeviceUnitModel.imei,
                LocationModel.name,
                EmployeeModel.full_name,
                number,
            )
            # Left throughout: a payment names no product, no handset and no
            # location, and it is still a row in the ledger.
            .outerjoin(
                ProductModel, ProductModel.id == FinancialTransactionModel.product_id
            )
            .outerjoin(
                DeviceUnitModel,
                DeviceUnitModel.id == FinancialTransactionModel.device_unit_id,
            )
            .outerjoin(
                LocationModel, LocationModel.id == FinancialTransactionModel.location_id
            )
            .outerjoin(
                EmployeeModel, EmployeeModel.id == FinancialTransactionModel.user_id
            )
        )
        if from_date is not None:
            stmt = stmt.where(FinancialTransactionModel.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(FinancialTransactionModel.occurred_at <= to_date)
        if txn_type is not None:
            stmt = stmt.where(FinancialTransactionModel.txn_type == txn_type.value)
        if location_id is not None:
            stmt = stmt.where(FinancialTransactionModel.location_id == location_id)
        if document_type is not None:
            stmt = stmt.where(
                FinancialTransactionModel.document_type == document_type.value
            )
        stmt = stmt.order_by(
            FinancialTransactionModel.occurred_at.desc(),
            FinancialTransactionModel.id,
        )

        return await self._page_rows(stmt, page, page_size, self._to_log_row)

    @staticmethod
    def _to_log_row(
        row: Row[
            tuple[FinancialTransactionModel, str, str, str, str, str | None]
        ],
    ) -> FinancialLedgerRow:
        txn, product, scanned, place, actor, number = row._tuple()
        # All four come off outer joins: a payment names no product, no
        # handset and no location, and it is still a row in the ledger.
        product_name: str | None = product
        imei: str | None = scanned
        location_name: str | None = place
        actor_name: str | None = actor
        return FinancialLedgerRow(
            id=txn.id,
            occurred_at=txn.occurred_at,
            txn_type=TransactionType(txn.txn_type),
            amount=Money(txn.amount_minor, Currency(txn.currency)),
            product_id=txn.product_id,
            product_name=product_name,
            device_unit_id=txn.device_unit_id,
            imei=imei,
            location_id=txn.location_id,
            location_name=location_name,
            document_type=DocumentType(txn.document_type),
            document_id=txn.document_id,
            document_number=number,
            actor=LedgerActor(user_id=txn.user_id, user_name=actor_name),
            note=txn.note,
        )

    async def sales_totals(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> list[SalesTotalsRow]:
        """FR-9.3's two categories, grouped by location and currency.

        Only ``SALE_REVENUE`` and ``COGS``: the report is about what selling
        earned, and a purchase or a write-off in the same window is not part
        of that answer.

        Dates are inclusive at both ends, like every other §5.9 report.
        ``totals_by_type``'s exclusive ``until`` is period math for §5.10 and
        is deliberately a different question with different parameter names.
        """
        stmt = (
            select(
                FinancialTransactionModel.location_id,
                LocationModel.name,
                FinancialTransactionModel.txn_type,
                FinancialTransactionModel.currency,
                func.sum(FinancialTransactionModel.amount_minor),
            )
            .outerjoin(
                LocationModel, LocationModel.id == FinancialTransactionModel.location_id
            )
            .where(
                FinancialTransactionModel.txn_type.in_(
                    [TransactionType.SALE_REVENUE.value, TransactionType.COGS.value]
                )
            )
            .group_by(
                FinancialTransactionModel.location_id,
                LocationModel.name,
                FinancialTransactionModel.txn_type,
                FinancialTransactionModel.currency,
            )
            .order_by(LocationModel.name)
        )
        if from_date is not None:
            stmt = stmt.where(FinancialTransactionModel.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(FinancialTransactionModel.occurred_at <= to_date)
        if location_id is not None:
            stmt = stmt.where(FinancialTransactionModel.location_id == location_id)
        return await self._many_rows(stmt, self._to_sales_total)

    @staticmethod
    def _to_sales_total(
        row: Row[tuple[UUID | None, str, str, str, int]],
    ) -> SalesTotalsRow:
        location_id, place, txn_type, currency_code, total = row._tuple()
        location_name: str | None = place
        return SalesTotalsRow(
            location_id=location_id,
            location_name=location_name,
            txn_type=TransactionType(txn_type),
            # Postgres widens SUM(BIGINT) to NUMERIC, and Money refuses
            # anything that is not an int.
            amount=Money(int(total or 0), Currency(currency_code)),
        )
