"""The reads the location use cases need, one class each.

Written against ``LocationModel``, not ``Location`` (ADR 0007). The browse
spec carries its filters as plain attributes so the in-memory fake can
read them without an ORM. The name-uniqueness probe is inline in the
create/update handlers.
"""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import LocationModel


class LocationForWrite(Specification[LocationModel]):
    """Locks the row so two concurrent renames cannot both pass the probe."""

    def __init__(self, location_id: UUID) -> None:
        super().__init__(LocationModel)
        self.location_id = location_id
        self.where(LocationModel.id == location_id)
        self.lock()


class LocationBrowse(Specification[LocationModel]):
    """The location list: case-insensitive match over name, optional active
    filter, oldest first (so seeded "Main Store" is always first)."""

    def __init__(self, search: str | None = None, is_active: bool | None = None) -> None:
        super().__init__(LocationModel)
        self.search = search
        self.is_active = is_active
        if search:
            self.where(LocationModel.name.ilike(f"%{search.strip()}%"))
        if is_active is not None:
            self.where(LocationModel.is_active.is_(is_active))
        self.order(LocationModel.created_at, LocationModel.id)
