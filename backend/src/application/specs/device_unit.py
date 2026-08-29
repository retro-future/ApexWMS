"""The reads the handset use cases need, one class each.

Written against ``DeviceUnitModel``, not ``DeviceUnit`` (ADR 0007). Every
spec eager-loads ``product`` for the currency the unit's money amounts are
denominated in (§4.5 rule 3).

The two report reads (ageing, needs-pricing) return projection rows, not
entities, so they live in a query service, not here.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import DeviceStatus
from infrastructure.persistence.tenant.models import DeviceUnitModel

_ON_HAND = [status.value for status in DeviceStatus if status.is_on_hand]
_WITH_PRODUCT = selectinload(DeviceUnitModel.product)


class DeviceUnitById(Specification[DeviceUnitModel]):
    """Read-only: no lock."""

    def __init__(self, device_unit_id: UUID) -> None:
        super().__init__(DeviceUnitModel)
        self.device_unit_id = device_unit_id
        self.where(DeviceUnitModel.id == device_unit_id)
        self.include(_WITH_PRODUCT)


class DeviceUnitForWrite(Specification[DeviceUnitModel]):
    """Locks the row for a command that loads a handset to move a
    projection (a posting or the repricer)."""

    def __init__(self, device_unit_id: UUID) -> None:
        super().__init__(DeviceUnitModel)
        self.device_unit_id = device_unit_id
        self.where(DeviceUnitModel.id == device_unit_id)
        self.include(_WITH_PRODUCT)
        self.lock()


class DeviceUnitByImei(Specification[DeviceUnitModel]):
    """FR-3.5/FR-7.1: what the scanner asks. IMEI is unique, one index hit."""

    def __init__(self, imei: str) -> None:
        super().__init__(DeviceUnitModel)
        self.imei = imei
        self.where(DeviceUnitModel.imei == imei)
        self.include(_WITH_PRODUCT)


class DeviceUnitsByIds(Specification[DeviceUnitModel]):
    """Bulk repricing's read (FR-2.21): every unit in one round trip."""

    def __init__(self, ids: Sequence[UUID]) -> None:
        super().__init__(DeviceUnitModel)
        self.ids = list(ids)
        self.where(DeviceUnitModel.id.in_(self.ids))
        self.include(_WITH_PRODUCT)


class OnHandDeviceUnits(Specification[DeviceUnitModel]):
    """Everything the store still physically holds (§4.6, FR-9.1),
    optionally at one location, oldest first."""

    def __init__(self, location_id: UUID | None = None) -> None:
        super().__init__(DeviceUnitModel)
        self.location_id = location_id
        self.where(DeviceUnitModel.status.in_(_ON_HAND))
        if location_id is not None:
            self.where(DeviceUnitModel.location_id == location_id)
        self.include(_WITH_PRODUCT)
        self.order(DeviceUnitModel.created_at)
