"""The MasterDB repository base.

The constructor demands ``MasterSession``, so a provider wiring a master
repository to a tenant session stops passing type checks instead of
failing at runtime.
"""

from abc import ABC
from uuid import UUID

from domain.core import Entity
from infrastructure.persistence.master.models.base import MasterBase
from infrastructure.persistence.repository import CrudRepository
from infrastructure.types import MasterSession


class MasterCrudRepository[EntityT: Entity, KeyT: UUID, ModelT: MasterBase](
    CrudRepository[EntityT, KeyT, ModelT], ABC
):
    def __init__(self, session: MasterSession) -> None:
        super().__init__(session)
