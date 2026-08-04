"""Response payload for one location — PRD §4.2: a store, a stockroom, a warehouse."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import Location


class LocationData(CamelModel):
    id: UUID
    name: str
    is_active: bool

    @classmethod
    def from_entity(cls, location: Location) -> LocationData:
        return cls(id=location.id, name=location.name, is_active=location.is_active)
