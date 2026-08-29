"""One mapper for every flat aggregate whose entity fields and ORM columns
share names and need no conversion.

An aggregate with a value object, an enum stored under a different
representation, or a child collection still gets a hand-written mapper.
"""

from dataclasses import fields
from typing import Any

from sqlalchemy.orm import DeclarativeBase

from domain.core import Entity


class AutoMapper[TEntity: Entity[Any], TModel: DeclarativeBase]:
    def __init__(self, entity_cls: type[TEntity], model_cls: type[TModel]) -> None:
        self.model = model_cls
        self._entity_cls = entity_cls
        self._names = tuple(f.name for f in fields(entity_cls))  # type: ignore[arg-type]

    def to_entity(self, model: TModel) -> TEntity:
        return self._entity_cls(**{name: getattr(model, name) for name in self._names})

    def to_model(self, entity: TEntity, model: TModel | None = None) -> TModel:
        model = model or self.model(id=entity.id)
        for name in self._names:
            setattr(model, name, getattr(entity, name))
        return model
