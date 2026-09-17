"""Money-ledger reads that group by currency and return a row or a dict
(§4.6). Split off ``SqlFinancialTransactionRepository`` when the aggregate
moved to the append-only generic repository.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Row, Select, bindparam, func, select
from sqlalchemy.dialects.postgresql import ARRAY

from application.dtos import FinancialLedgerRow, LedgerActor, SalesTotalsRow
from domain.enums import DocumentType, TransactionType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    EmployeeModel,
    FinancialTransactionModel,
    LocationModel,
    ProductModel,
)
from infrastructure.persistence.tenant.queries.document_ref import document_number
from infrastructure.types import TenantSession

_T = FinancialTransactionModel


class SqlFinancialTransactionQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def totals_by_type(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency], Money]:
        """Every category's net, per currency. *until* is exclusive so a
        period is ``[start, next start)`` (FR-10.8)."""
        stmt = select(_T.txn_type, _T.currency, func.sum(_T.amount_minor)).group_by(
            _T.txn_type, _T.currency
        )
        if since is not None:
            stmt = stmt.where(_T.occurred_at >= since)
        if until is not None:
            stmt = stmt.where(_T.occurred_at < until)
        if location_id is not None:
            stmt = stmt.where(_T.location_id == location_id)
        rows = await self._session.execute(stmt)
        # Postgres widens SUM(BIGINT) to NUMERIC; Money refuses non-int.
        return {
            (TransactionType(txn_type), Currency(currency)): Money(
                int(total or 0), Currency(currency)
            )
            for txn_type, currency, total in rows
        }

    async def totals_by_type_and_rate(
        self,
        *,
        rate_changes: Sequence[datetime],
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency, datetime | None], Money]:
        """``totals_by_type`` split at each rate change.

        ``width_bucket`` returns 0 before the first change and *i* from the
        *i*-th one on, so the rows stay one per category per quote rather
        than one per transaction.
        """
        changes = list(rate_changes)
        bucket = func.width_bucket(
            _T.occurred_at,
            bindparam("rate_changes", changes, type_=ARRAY(DateTime(timezone=True))),
        ).label("bucket")
        stmt = select(
            _T.txn_type, _T.currency, bucket, func.sum(_T.amount_minor)
        ).group_by(_T.txn_type, _T.currency, bucket)
        if since is not None:
            stmt = stmt.where(_T.occurred_at >= since)
        if until is not None:
            stmt = stmt.where(_T.occurred_at < until)
        if location_id is not None:
            stmt = stmt.where(_T.location_id == location_id)
        rows = await self._session.execute(stmt)
        return {
            (
                TransactionType(txn_type),
                Currency(currency),
                None if index == 0 else changes[index - 1],
            ): Money(int(total or 0), Currency(currency))
            for txn_type, currency, index, total in rows
        }

    async def sales_totals(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> list[SalesTotalsRow]:
        """FR-9.3's three categories, grouped by location and currency.

        ``SALES_RETURN_REFUND`` joins the original two so gross revenue and
        what came back are both visible: a return nets ``COGS`` down on its
        own, so leaving the refund out would report the margin too high.
        Dates inclusive at both ends.
        """
        stmt = (
            select(
                _T.location_id,
                LocationModel.name,
                _T.txn_type,
                _T.currency,
                func.sum(_T.amount_minor),
            )
            .outerjoin(LocationModel, LocationModel.id == _T.location_id)
            .where(
                _T.txn_type.in_(
                    [
                        TransactionType.SALE_REVENUE.value,
                        TransactionType.COGS.value,
                        TransactionType.SALES_RETURN_REFUND.value,
                    ]
                )
            )
            .group_by(_T.location_id, LocationModel.name, _T.txn_type, _T.currency)
            .order_by(LocationModel.name)
        )
        if from_date is not None:
            stmt = stmt.where(_T.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(_T.occurred_at <= to_date)
        if location_id is not None:
            stmt = stmt.where(_T.location_id == location_id)
        rows = await self._session.execute(stmt)
        return [self._to_sales_total(row) for row in rows]

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
        """FR-10.3: the raw money ledger, newest first. A log, no total —
        these rows mix currencies by design (§4.5 rule 4)."""
        number = document_number(_T.document_type, _T.document_id)
        stmt = (
            select(
                _T,
                ProductModel.name,
                DeviceUnitModel.imei,
                LocationModel.name,
                EmployeeModel.full_name,
                number,
            )
            # Left throughout: a payment names no product, handset or location.
            .outerjoin(ProductModel, ProductModel.id == _T.product_id)
            .outerjoin(DeviceUnitModel, DeviceUnitModel.id == _T.device_unit_id)
            .outerjoin(LocationModel, LocationModel.id == _T.location_id)
            .outerjoin(EmployeeModel, EmployeeModel.id == _T.user_id)
        )
        if from_date is not None:
            stmt = stmt.where(_T.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(_T.occurred_at <= to_date)
        if txn_type is not None:
            stmt = stmt.where(_T.txn_type == txn_type.value)
        if location_id is not None:
            stmt = stmt.where(_T.location_id == location_id)
        if document_type is not None:
            stmt = stmt.where(_T.document_type == document_type.value)
        stmt = stmt.order_by(_T.occurred_at.desc(), _T.id)

        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_log_row(row) for row in rows], total

    async def _count(self, stmt: Select[Any]) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        return total or 0

    @staticmethod
    def _to_sales_total(row: Row[tuple[UUID | None, str, str, str, int]]) -> SalesTotalsRow:
        location_id, place, txn_type, currency_code, total = row._tuple()
        location_name: str | None = place
        return SalesTotalsRow(
            location_id=location_id,
            location_name=location_name,
            txn_type=TransactionType(txn_type),
            amount=Money(int(total or 0), Currency(currency_code)),
        )

    @staticmethod
    def _to_log_row(
        row: Row[tuple[FinancialTransactionModel, str, str, str, str, str | None]],
    ) -> FinancialLedgerRow:
        txn, product, scanned, place, actor, number = row._tuple()
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
