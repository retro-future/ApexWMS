"""A handset's markdown history (FR-2.15, §4.5b).

Two joins deep, for the same reason the catalog log needs one: the amounts
are bare minor units, and the currency belongs to the *product* the unit
points at (§4.5 rule 3). Denormalizing it onto the log row would be a
third copy of a fact that is already immutable in one place.
"""

from uuid import UUID

from sqlalchemy import Select, select

from domain.entities import DeviceUnitPriceChange
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    DeviceUnitPriceChangeModel,
    ProductModel,
)

from .base import TenantLedgerRepository


class SqlDeviceUnitPriceChangeRepository(
    TenantLedgerRepository[DeviceUnitPriceChange, DeviceUnitPriceChangeModel]
):
    model = DeviceUnitPriceChangeModel

    def _to_model(self, entity: DeviceUnitPriceChange) -> DeviceUnitPriceChangeModel:
        return DeviceUnitPriceChangeModel(
            id=entity.id,
            device_unit_id=entity.device_unit_id,
            occurred_at=entity.occurred_at,
            old_price_minor=entity.old_price.amount_minor if entity.old_price else None,
            new_price_minor=entity.new_price.amount_minor,
            reason=entity.reason,
            user_id=entity.user_id,
        )

    def _to_entity(
        self, row: DeviceUnitPriceChangeModel, currency: Currency
    ) -> DeviceUnitPriceChange:
        return DeviceUnitPriceChange(
            id=row.id,
            device_unit_id=row.device_unit_id,
            occurred_at=row.occurred_at,
            old_price=(
                Money(row.old_price_minor, currency) if row.old_price_minor is not None else None
            ),
            new_price=Money(row.new_price_minor, currency),
            reason=row.reason,
            user_id=row.user_id,
        )

    async def list_for_unit(self, device_unit_id: UUID) -> list[DeviceUnitPriceChange]:
        """One handset's whole pricing timeline, oldest first (FR-9.2)."""
        rows = await self._session.execute(self._priced(device_unit_id))
        return [self._to_entity(row, Currency(currency)) for row, currency in rows]

    async def latest_for_unit(self, device_unit_id: UUID) -> DeviceUnitPriceChange | None:
        """The row ``DeviceUnit.asking_price`` is the projection of."""
        stmt = self._priced(device_unit_id).order_by(
            DeviceUnitPriceChangeModel.occurred_at.desc(),
            DeviceUnitPriceChangeModel.id.desc(),
        )
        found = (await self._session.execute(stmt.limit(1))).first()
        if found is None:
            return None
        row, currency = found
        return self._to_entity(row, Currency(currency))

    async def count_for_unit(self, device_unit_id: UUID) -> int:
        """How many times this handset has been marked down (FR-9.4).

        A unit cut twice that still has not moved is the sharpest form of
        the phone retailer's core financial risk, so the ageing report
        reports the count rather than making the reader infer it.
        """
        rows = await self._session.scalars(
            select(DeviceUnitPriceChangeModel.id).where(
                DeviceUnitPriceChangeModel.device_unit_id == device_unit_id
            )
        )
        return len(rows.all())

    def _priced(
        self, device_unit_id: UUID
    ) -> Select[tuple[DeviceUnitPriceChangeModel, str]]:
        """Rows for one unit, oldest first, each with its currency.

        The tie-break on ``id`` is not cosmetic: two markdowns inside the
        same clock tick would otherwise order arbitrarily, and "which was
        the latest price" is exactly the question the projection asks.
        """
        return (
            select(DeviceUnitPriceChangeModel, ProductModel.currency)
            .join(
                DeviceUnitModel,
                DeviceUnitModel.id == DeviceUnitPriceChangeModel.device_unit_id,
            )
            .join(ProductModel, ProductModel.id == DeviceUnitModel.product_id)
            .where(DeviceUnitPriceChangeModel.device_unit_id == device_unit_id)
            .order_by(
                DeviceUnitPriceChangeModel.occurred_at, DeviceUnitPriceChangeModel.id
            )
        )
