"""The generic repository narrowed to the platform database.

The mirror of ``tenant.py``: the constructor demands ``MasterSession``, so
a provider wiring a master repository to a tenant session stops passing
type checks instead of failing at runtime.
"""

from application.common.mapper import EntityMapper
from domain.core import Entity
from infrastructure.persistence.master.models.base import MasterBase
from infrastructure.persistence.repositories.base import SqlAlchemyRepository
from infrastructure.types import MasterSession


class MasterSqlRepository[EntityT: Entity, ModelT: MasterBase](
    SqlAlchemyRepository[EntityT, ModelT]
):
    """``SqlAlchemyRepository`` against the platform database. It adds only
    the narrowed constructor, so a ``TenantSession`` handed here is a type
    error and the container cannot cross the two databases."""

    def __init__(
        self,
        session: MasterSession,
        model_cls: type[ModelT],
        mapper: EntityMapper[EntityT, ModelT],
    ) -> None:
        super().__init__(session, model_cls, mapper)
