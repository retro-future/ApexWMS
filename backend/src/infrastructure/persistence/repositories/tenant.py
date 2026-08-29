"""The generic repository narrowed to a tenant's database.

Both narrow their constructor to ``TenantSession``, which is the whole
reason they exist as separate classes: a ``MasterSession`` is then a type
error here, so the container physically cannot hand a store's repository
the platform's database. ``ty`` is the only thing that enforces it, a
``NewType`` being an identity function at runtime, which is why a red type
check is a broken build.
"""

from application.common.mapper import EntityMapper
from domain.core import Entity
from infrastructure.persistence.repositories.base import (
    SqlAlchemyRepository,
    SqlAppendOnlyRepository,
)
from infrastructure.persistence.tenant.models.base import TenantBase
from infrastructure.types import TenantSession


class TenantSqlAppendOnlyRepository[EntityT: Entity, ModelT: TenantBase](
    SqlAppendOnlyRepository[EntityT, ModelT]
):
    """``SqlAppendOnlyRepository`` against this tenant's database — the
    ledgers and logs. No ``update``/``delete`` in the type."""

    def __init__(
        self,
        session: TenantSession,
        model_cls: type[ModelT],
        mapper: EntityMapper[EntityT, ModelT],
    ) -> None:
        super().__init__(session, model_cls, mapper)


class TenantSqlRepository[EntityT: Entity, ModelT: TenantBase](
    SqlAlchemyRepository[EntityT, ModelT]
):
    """``SqlAlchemyRepository`` against this tenant's database. It adds
    nothing but the narrowed constructor, which is the point."""

    def __init__(
        self,
        session: TenantSession,
        model_cls: type[ModelT],
        mapper: EntityMapper[EntityT, ModelT],
    ) -> None:
        super().__init__(session, model_cls, mapper)
