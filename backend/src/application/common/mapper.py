"""The port between a domain entity and its ORM row.

``to_model``'s optional second argument is the whole point: passed a
persistent row, an implementation copies onto it instead of building a new
one, which is what keeps SQLAlchemy's change tracking working. Passed
nothing, it builds the row an ``add`` inserts.

``model`` is how a mapper names the table it is for, so the container can
find the right one from a model class alone. That is what lets one generic
repository factory serve every aggregate.
"""

from typing import Protocol


class EntityMapper[TEntity, TModel](Protocol):
    model: type[TModel]

    def to_entity(self, model: TModel) -> TEntity: ...

    def to_model(self, entity: TEntity, model: TModel | None = None) -> TModel: ...
