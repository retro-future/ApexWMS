"""Handsets (PRD §4.2).

Every read joins ``products``: a unit's cost and asking price are bare
minor units denominated by its catalog row (§4.5 rule 3), so the currency
is fetched rather than duplicated onto the unit — where it could drift.
That is also why the entity is rebuilt from a ``Row`` and not from the unit
row alone, and so why this is not a ``TenantCrudRepository``.

``update`` writes ``status``, ``location_id`` and ``asking_price_minor``,
which look like ordinary mutable fields and are not: all three are
projections kept in step by the ledger posting and the repricer. Nothing
else may assign them.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Row, Select, select

from domain.entities import DeviceUnit
from domain.enums import DeviceCondition, DeviceStatus, DocumentType
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import DeviceUnitModel, ProductModel

from .base import TenantRepository


class SqlDeviceUnitRepository(TenantRepository):
    def _to_model(self, entity: DeviceUnit) -> DeviceUnitModel:
        return DeviceUnitModel(
            id=entity.id,
            imei=str(entity.imei),
            imei2=str(entity.imei2) if entity.imei2 else None,
            serial_number=entity.serial_number,
            product_id=entity.product_id,
            status=entity.status.value,
            location_id=entity.location_id,
            acquisition_cost_minor=entity.acquisition_cost.amount_minor,
            asking_price_minor=(
                entity.asking_price.amount_minor if entity.asking_price else None
            ),
            condition=entity.condition.value,
            cash_paid_minor=entity.cash_paid_minor,
            cash_paid_currency=(
                entity.cash_paid_currency.value if entity.cash_paid_currency else None
            ),
            source_document_type=(
                entity.source_document_type.value if entity.source_document_type else None
            ),
            source_document_id=entity.source_document_id,
            created_at=entity.created_at,
        )

    def _to_entity(self, row: Row[tuple[DeviceUnitModel, str]]) -> DeviceUnit:
        unit, currency_code = row._tuple()
        currency = Currency(currency_code)
        return DeviceUnit(
            id=unit.id,
            imei=IMEI(unit.imei),
            imei2=IMEI(unit.imei2) if unit.imei2 else None,
            serial_number=unit.serial_number,
            product_id=unit.product_id,
            status=DeviceStatus(unit.status),
            location_id=unit.location_id,
            acquisition_cost=Money(unit.acquisition_cost_minor, currency),
            asking_price=(
                Money(unit.asking_price_minor, currency)
                if unit.asking_price_minor is not None
                else None
            ),
            condition=DeviceCondition(unit.condition),
            cash_paid_minor=unit.cash_paid_minor,
            # The one amount on the row that is *not* in the product's currency,
            # which is the entire reason it is recorded separately (§4.5b).
            cash_paid_currency=(
                Currency(unit.cash_paid_currency) if unit.cash_paid_currency else None
            ),
            source_document_type=(
                DocumentType(unit.source_document_type)
                if unit.source_document_type
                else None
            ),
            source_document_id=unit.source_document_id,
            created_at=unit.created_at,
        )

    async def get(self, key: UUID) -> DeviceUnit | None:
        return await self._one_row(
            self._joined().where(DeviceUnitModel.id == key), self._to_entity
        )

    async def add(self, entity: DeviceUnit) -> None:
        await self._insert(self._to_model(entity))

    async def update(self, entity: DeviceUnit) -> None:
        row = await self._require_row(DeviceUnitModel, entity.id)
        # The IMEI, the product, the cost and the acquisition provenance are
        # absent on purpose: none of them can change about a handset that has
        # already been received. A wrong one is corrected by cancelling the
        # receipt (§4.4), not by patching the unit.
        row.status = entity.status.value
        row.location_id = entity.location_id
        row.asking_price_minor = (
            entity.asking_price.amount_minor if entity.asking_price else None
        )
        row.condition = entity.condition.value

    async def get_by_imei(self, imei: str) -> DeviceUnit | None:
        """FR-3.5/FR-7.1: the scanner's question, answered by one index hit."""
        return await self._one_row(
            self._joined().where(DeviceUnitModel.imei == imei), self._to_entity
        )

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[DeviceUnit]:
        """The bulk repricing's read (FR-2.21), in one round trip.

        One statement rather than a loop, because the call is atomic: every
        unit has to be in hand before any of them is priced.
        """
        if not ids:
            return []
        return await self._many_rows(
            self._joined().where(DeviceUnitModel.id.in_(ids)), self._to_entity
        )

    async def list_on_hand(self, location_id: UUID | None = None) -> list[DeviceUnit]:
        """Everything the store still physically holds (§4.6, FR-9.1).

        The basis of on-hand inventory value and of the needs-pricing
        worklist, so the filter lives here rather than in each caller.
        """
        stmt = self._joined().where(
            DeviceUnitModel.status.in_([s.value for s in DeviceStatus if s.is_on_hand])
        )
        if location_id is not None:
            stmt = stmt.where(DeviceUnitModel.location_id == location_id)
        return await self._many_rows(
            stmt.order_by(DeviceUnitModel.created_at), self._to_entity
        )

    def _joined(self) -> Select[tuple[DeviceUnitModel, str]]:
        return select(DeviceUnitModel, ProductModel.currency).join(
            ProductModel, ProductModel.id == DeviceUnitModel.product_id
        )
