"""Entity mappers (APP scope).

A mapper holds no session and no state, so one instance serves every
request and one registry serves both databases. They are registered as a
``MapperRegistry`` keyed by model class rather than one DI key each,
because that is what a *generic* repository factory can look one up
from: it is handed ``type[M]`` and nothing else.

``for_model`` is the bridge that makes the generic factory build at all.
Dishka binds a free typevar from ``type[M]``, but it resolves a
*dependency* by exact key — a factory asking for ``EntityMapper[E, M]``
needs something registered under that literal type, which a concrete
``EntityMapper[Supplier, SupplierModel]`` is not.

The trade: the entity/model pairing is checked when the registry is built,
not by ``ty`` at each call site. ``TenantDbRepository[Location,
SupplierModel]`` resolves and hands back a ``SupplierMapper``. An
unconverted model raises ``UnmappedModelError``, which names the fix.
"""

from typing import TypeVar, cast

from dishka import Provider, Scope, provide
from sqlalchemy.orm import DeclarativeBase

from application.common.mapper import EntityMapper
from domain.core import Entity
from infrastructure.persistence.mappers import COMMON_MAPPERS, MapperRegistry

E = TypeVar("E", bound=Entity)
M = TypeVar("M", bound=DeclarativeBase)


class MapperProvider(Provider):
    scope = Scope.APP

    @provide
    def registry(self) -> MapperRegistry:
        return MapperRegistry(*COMMON_MAPPERS)

    @provide
    def for_model(self, registry: MapperRegistry, model_cls: type[M]) -> EntityMapper[E, M]:
        return cast(EntityMapper[E, M], registry.for_model(model_cls))
