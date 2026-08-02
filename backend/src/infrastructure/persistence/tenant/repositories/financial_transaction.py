"""The money ledger (PRD §4.6).

The one tenant table that stores its own currency, because a transaction
need not belong to a product: a ``PAYMENT_RECEIVED`` entry is som against
an invoice whose lines may be dollars (§4.7). So no join, and every
aggregate here **groups by currency** — a ``SUM`` that forgot to would add
cents to som.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from domain.entities import FinancialTransaction
from domain.enums import DocumentType, TransactionType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import FinancialTransactionModel

from .base import TenantLedgerRepository


class SqlFinancialTransactionRepository(
    TenantLedgerRepository[FinancialTransaction, FinancialTransactionModel]
):
    model = FinancialTransactionModel

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

    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[FinancialTransaction]:
        """Everything one document booked — what a cancellation reverses."""
        return await self._find_many(
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
        return await self._find_many(
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
