"""Model class → the mapper that builds its aggregate.

One registry for both databases. A mapper never touches a session, so
there is nothing master- or tenant-specific to separate, and a model
class is unique across the two schemas anyway (``MasterBase`` and
``TenantBase`` own separate metadata).

The lookup a generic repository factory needs: given only the ORM model
bound to ``TModel``, hand back the mapper for it. Each mapper names its own
table through ``EntityMapper.model``, so registering one is adding it to
``COMMON_MAPPERS`` and nothing else.
"""

from typing import Any

from application.common.mapper import EntityMapper


class UnmappedModelError(LookupError):
    """No mapper claims this model — it has not been converted yet."""

    def __init__(self, model_cls: type[Any]) -> None:
        super().__init__(
            f"{model_cls.__name__} has no EntityMapper; add one to COMMON_MAPPERS"
        )


class MapperRegistry:
    def __init__(self, *mappers: EntityMapper[Any, Any]) -> None:
        self._by_model: dict[type[Any], EntityMapper[Any, Any]] = {
            mapper.model: mapper for mapper in mappers
        }

    def for_model(self, model_cls: type[Any]) -> EntityMapper[Any, Any]:
        try:
            return self._by_model[model_cls]
        except KeyError:
            raise UnmappedModelError(model_cls) from None
