"""A handset's markdown log reads (FR-2.15, FR-9.2).

Written against ``DeviceUnitPriceChangeModel`` (ADR 0007). The amounts carry
no currency; it is reached ``device_unit -> product`` (§4.5 rule 3), so
every read chains two ``selectinload``s. Both specs store ``device_unit_id``
as a plain attribute for the in-memory fake.
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    DeviceUnitPriceChangeModel,
)

_WITH_CURRENCY = selectinload(DeviceUnitPriceChangeModel.device_unit).selectinload(
    DeviceUnitModel.product
)


class PriceChangesForUnit(Specification[DeviceUnitPriceChangeModel]):
    """One handset's whole pricing timeline, oldest first."""

    def __init__(self, device_unit_id: UUID) -> None:
        super().__init__(DeviceUnitPriceChangeModel)
        self.device_unit_id = device_unit_id
        self.where(DeviceUnitPriceChangeModel.device_unit_id == device_unit_id)
        self.include(_WITH_CURRENCY)
        self.order(
            DeviceUnitPriceChangeModel.occurred_at, DeviceUnitPriceChangeModel.id
        )


class LatestPriceChangeForUnit(Specification[DeviceUnitPriceChangeModel]):
    """The row ``DeviceUnit.asking_price`` is the projection of; used with
    ``find_one``."""

    def __init__(self, device_unit_id: UUID) -> None:
        super().__init__(DeviceUnitPriceChangeModel)
        self.device_unit_id = device_unit_id
        self.where(DeviceUnitPriceChangeModel.device_unit_id == device_unit_id)
        self.include(_WITH_CURRENCY)
        self.order(
            DeviceUnitPriceChangeModel.occurred_at.desc(),
            DeviceUnitPriceChangeModel.id.desc(),
        )
