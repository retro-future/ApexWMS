"""A handset's markdown history (FR-2.15, §4.5b).

Two joins deep, for the same reason the catalog log needs one: the amounts
are bare minor units, and the currency belongs to the *product* the unit
points at (§4.5 rule 3). Denormalizing it onto the log row would be a
third copy of a fact that is already immutable in one place.
"""

from uuid import UUID

from sqlalchemy import Row, Select, func, select

from domain.entities import DeviceUnitPriceChange
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    DeviceUnitPriceChangeModel,
    ProductModel,
)

from .base import TenantRepository


class SqlDeviceUnitPriceChangeRepository(TenantRepository):
    """Append and read; never update — the port says so (§4.5b)."""

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
        self, row: Row[tuple[DeviceUnitPriceChangeModel, str]]
    ) -> DeviceUnitPriceChange:
        change, currency_code = row._tuple()
        currency = Currency(currency_code)
        return DeviceUnitPriceChange(
            id=change.id,
            device_unit_id=change.device_unit_id,
            occurred_at=change.occurred_at,
            old_price=(
                Money(change.old_price_minor, currency)
                if change.old_price_minor is not None
                else None
            ),
            new_price=Money(change.new_price_minor, currency),
            reason=change.reason,
            user_id=change.user_id,
        )

    async def add(self, entity: DeviceUnitPriceChange) -> None:
        await self._insert(self._to_model(entity))

    async def list_for_unit(self, device_unit_id: UUID) -> list[DeviceUnitPriceChange]:
        """One handset's whole pricing timeline, oldest first (FR-9.2)."""
        return await self._many_rows(self._priced(device_unit_id), self._to_entity)

    async def latest_for_unit(self, device_unit_id: UUID) -> DeviceUnitPriceChange | None:
        """The row ``DeviceUnit.asking_price`` is the projection of."""
        # ``order_by(None)`` first: SQLAlchemy *appends* to an existing
        # ORDER BY, so without the reset the ascending clauses `_priced`
        # already carries would win and LIMIT 1 would return the oldest.
        stmt = (
            self._priced(device_unit_id)
            .order_by(None)
            .order_by(
                DeviceUnitPriceChangeModel.occurred_at.desc(),
                DeviceUnitPriceChangeModel.id.desc(),
            )
            .limit(1)
        )
        return await self._one_row(stmt, self._to_entity)

    async def count_for_unit(self, device_unit_id: UUID) -> int:
        """How many times this handset has been marked down (FR-9.4).

        A unit cut twice that still has not moved is the sharpest form of
        the phone retailer's core financial risk, so the ageing report
        reports the count rather than making the reader infer it.
        """
        count = await self._session.scalar(
            select(func.count())
            .select_from(DeviceUnitPriceChangeModel)
            .where(DeviceUnitPriceChangeModel.device_unit_id == device_unit_id)
        )
        return count or 0

    def _priced(self, device_unit_id: UUID) -> Select[tuple[DeviceUnitPriceChangeModel, str]]:
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
