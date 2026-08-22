"""Money received against store credit (PRD §4.7).

Append and read. No ``update`` and no ``delete``: a mistaken payment is
compensated by a negative one (FR-11.8), the same discipline both ledgers
keep.

No currency join and no currency column — every customer debt in the
system is som (§4.7), so ``amount_minor`` is a som amount and the
conversion is a constant.
"""

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from domain.entities import Payment
from domain.enums import PaymentMethod
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import PaymentModel

from .base import TenantRepository


class SqlPaymentRepository(TenantRepository):
    async def add(self, entity: Payment) -> None:
        await self._insert(self._to_model(entity))

    async def get(self, payment_id: UUID) -> Payment | None:
        row = await self._row(PaymentModel, payment_id)
        return None if row is None else self._to_entity(row)

    async def list_for_invoice(self, sales_invoice_id: UUID) -> list[Payment]:
        return await self._many(
            select(PaymentModel)
            .where(PaymentModel.sales_invoice_id == sales_invoice_id)
            .order_by(PaymentModel.occurred_at, PaymentModel.id),
            self._to_entity,
        )

    async def list_for_invoices(
        self, sales_invoice_ids: Sequence[UUID]
    ) -> dict[UUID, list[Payment]]:
        found: defaultdict[UUID, list[Payment]] = defaultdict(list)
        if not sales_invoice_ids:
            return found

        rows = await self._many(
            select(PaymentModel)
            .where(PaymentModel.sales_invoice_id.in_(sales_invoice_ids))
            .order_by(PaymentModel.occurred_at, PaymentModel.id),
            self._to_entity,
        )
        for payment in rows:
            found[payment.sales_invoice_id].append(payment)
        return found

    async def paid_for(self, sales_invoice_id: UUID) -> Money:
        total = await self._session.scalar(
            select(func.sum(PaymentModel.amount_minor)).where(
                PaymentModel.sales_invoice_id == sales_invoice_id
            )
        )
        return self._som(total)

    async def reversal_of(self, payment_id: UUID) -> Payment | None:
        return await self._one(
            select(PaymentModel).where(PaymentModel.reverses_payment_id == payment_id),
            self._to_entity,
        )

    async def list_all(self) -> list[Payment]:
        return await self._many(
            select(PaymentModel).order_by(PaymentModel.occurred_at, PaymentModel.id),
            self._to_entity,
        )

    @staticmethod
    def _som(total: int | Decimal | None) -> Money:
        """A summed som amount, as ``Money``.

        Postgres widens ``SUM(BIGINT)`` to ``NUMERIC`` and asyncpg hands
        that back as a ``Decimal``, which ``Money`` refuses. Every summand
        was a whole som, so the conversion is lossless — it is the driver's
        type being corrected, not the value.
        """
        return Money(int(total or 0), Currency.UZS)

    @staticmethod
    def _to_model(entity: Payment) -> PaymentModel:
        return PaymentModel(
            id=entity.id,
            sales_invoice_id=entity.sales_invoice_id,
            occurred_at=entity.occurred_at,
            amount_minor=entity.amount.amount_minor,
            method=entity.method.value,
            user_id=entity.user_id,
            note=entity.note,
            reverses_payment_id=entity.reverses_payment_id,
        )

    @staticmethod
    def _to_entity(row: PaymentModel) -> Payment:
        return Payment(
            id=row.id,
            sales_invoice_id=row.sales_invoice_id,
            occurred_at=row.occurred_at,
            amount=Money(row.amount_minor, Currency.UZS),
            method=PaymentMethod(row.method),
            user_id=row.user_id,
            note=row.note,
            reverses_payment_id=row.reverses_payment_id,
        )
