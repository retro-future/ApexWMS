"""TenantDB repositories, specification-based (REQUEST scope).

One factory for every tenant aggregate. Dishka binds ``E`` and ``M`` from
the requested ``TenantDbRepository[Supplier, SupplierModel]``, hands the
concrete model class in through ``type[M]``, and resolves the mapper
through ``mappers.py``'s ``for_model`` — so converting an aggregate adds a
mapper and a name in ``COMMON_MAPPERS``, and nothing here.

``TenantDbRepository`` rather than the bare ``Repository`` is what lets the
master side have a factory of its own: one key can only be served once, and
that one factory would have to take a plain ``AsyncSession``, erasing the
``MasterSession``/``TenantSession`` distinction ``ty`` is the only thing
enforcing (``docs/architecture/multi-tenancy.md``). ``M`` is bound to
``TenantBase`` for the same reason — a master model requested here does not
type-check.
"""

from typing import TypeVar

from dishka import Provider, Scope, provide

from application.common.mapper import EntityMapper
from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from domain.core import Entity
from infrastructure.persistence.repositories import (
    TenantSqlAppendOnlyRepository,
    TenantSqlRepository,
)
from infrastructure.persistence.tenant.models.base import TenantBase
from infrastructure.types import TenantSession

E = TypeVar("E", bound=Entity)
M = TypeVar("M", bound=TenantBase)


class TenantRepositoryProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def tenant_repository(
        self,
        session: TenantSession,
        model_cls: type[M],
        mapper: EntityMapper[E, M],
    ) -> TenantDbRepository[E, M]:
        return TenantSqlRepository(session, model_cls, mapper)

    @provide
    def tenant_append_only_repository(
        self,
        session: TenantSession,
        model_cls: type[M],
        mapper: EntityMapper[E, M],
    ) -> TenantAppendOnlyRepository[E, M]:
        return TenantSqlAppendOnlyRepository(session, model_cls, mapper)
