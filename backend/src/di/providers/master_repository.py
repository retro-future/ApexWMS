"""MasterDB repositories, specification-based (REQUEST scope).

The mirror of ``tenant_repository.py`` for the platform database. Dishka
binds ``E`` and ``M`` from the requested ``MasterDbRepository[User,
UserModel]``, hands the model class in through ``type[M]``, and resolves
the mapper through ``mappers.py``'s ``for_model`` — so converting a master
aggregate adds a mapper and a name in ``COMMON_MAPPERS``, and nothing here.

``M`` is bound to ``MasterBase`` so a tenant model requested here does not
type-check, the same guard ``TenantRepositoryProvider`` has in reverse.
"""

from typing import TypeVar

from dishka import Provider, Scope, provide

from application.common.mapper import EntityMapper
from application.common.repository import MasterDbRepository
from domain.core import Entity
from infrastructure.persistence.master.models.base import MasterBase
from infrastructure.persistence.repositories import MasterSqlRepository
from infrastructure.types import MasterSession

E = TypeVar("E", bound=Entity)
M = TypeVar("M", bound=MasterBase)


class MasterRepositoryProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def master_repository(
        self,
        session: MasterSession,
        model_cls: type[M],
        mapper: EntityMapper[E, M],
    ) -> MasterDbRepository[E, M]:
        return MasterSqlRepository(session, model_cls, mapper)
