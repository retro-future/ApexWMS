"""Handsets (PRD §4.2).

Every read joins ``products``: a unit's cost and asking price are bare
minor units denominated by its catalog row (§4.5 rule 3), so the currency
is fetched rather than duplicated onto the unit — where it could drift.

``_apply`` writes ``status``, ``location_id`` and ``asking_price_minor``,
which look like ordinary mutable fields and are not: all three are
projections kept in step by the ledger posting and the repricer. Nothing
else may assign them.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select

from domain.entities import DeviceUnit
from domain.enums import DeviceCondition, DeviceStatus, DocumentType
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import DeviceUnitModel, ProductModel

from .base import TenantJoinedRepository


class SqlDeviceUnitRepository(TenantJoinedRepository[DeviceUnit, UUID, DeviceUnitModel]):
    model = DeviceUnitModel

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

    def _apply(self, row: DeviceUnitModel, entity: DeviceUnit) -> None:
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

    async def get(self, key: UUID) -> DeviceUnit | None:
        return await self._one(self._joined().where(DeviceUnitModel.id == key))

    async def get_by_imei(self, imei: str) -> DeviceUnit | None:
        """FR-3.5/FR-7.1: the scanner's question, answered by one index hit."""
        return await self._one(self._joined().where(DeviceUnitModel.imei == imei))

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[DeviceUnit]:
        """The bulk repricing's read (FR-2.21), in one round trip.

        One statement rather than a loop, because the call is atomic: every
        unit has to be in hand before any of them is priced.
        """
        if not ids:
            return []
        return await self._many(self._joined().where(DeviceUnitModel.id.in_(ids)))

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
        return await self._many(stmt.order_by(DeviceUnitModel.created_at))

    def _joined(self) -> Select[tuple[DeviceUnitModel, str]]:
        return select(DeviceUnitModel, ProductModel.currency).join(
            ProductModel, ProductModel.id == DeviceUnitModel.product_id
        )

    async def _one(self, stmt: Select[tuple[DeviceUnitModel, str]]) -> DeviceUnit | None:
        found = (await self._session.execute(stmt)).first()
        return None if found is None else _hydrate(found[0], Currency(found[1]))

    async def _many(self, stmt: Select[tuple[DeviceUnitModel, str]]) -> list[DeviceUnit]:
        rows = await self._session.execute(stmt)
        return [_hydrate(row, Currency(currency)) for row, currency in rows]


def _hydrate(row: DeviceUnitModel, currency: Currency) -> DeviceUnit:
    return DeviceUnit(
        id=row.id,
        imei=IMEI(row.imei),
        imei2=IMEI(row.imei2) if row.imei2 else None,
        serial_number=row.serial_number,
        product_id=row.product_id,
        status=DeviceStatus(row.status),
        location_id=row.location_id,
        acquisition_cost=Money(row.acquisition_cost_minor, currency),
        asking_price=(
            Money(row.asking_price_minor, currency)
            if row.asking_price_minor is not None
            else None
        ),
        condition=DeviceCondition(row.condition),
        cash_paid_minor=row.cash_paid_minor,
        # The one amount on the row that is *not* in the product's currency,
        # which is the entire reason it is recorded separately (§4.5b).
        cash_paid_currency=(
            Currency(row.cash_paid_currency) if row.cash_paid_currency else None
        ),
        source_document_type=(
            DocumentType(row.source_document_type) if row.source_document_type else None
        ),
        source_document_id=row.source_document_id,
        created_at=row.created_at,
    )
