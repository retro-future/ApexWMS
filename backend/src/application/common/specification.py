"""A query, as an object: the filters, joins, eager loads and ordering one
read needs, carried from the use case into the repository.

Written against ORM models rather than domain classes, deliberately — see
ADR 0007. That is what keeps ``ty check`` able to see every predicate.

There is no ``columns``/``group_by``/``having`` here on purpose: a
specification selects whole entities. A read that projects or aggregates is
a different kind of thing and belongs in its own query service.
"""

from typing import Any, Self

from sqlalchemy import ColumnElement, ColumnExpressionArgument
from sqlalchemy.sql.base import ExecutableOption


class Specification[TModel]:
    """The fluent builders mutate and return ``self``, so a specification
    handed to both ``count`` and ``find`` must be counted **before**
    ``page()`` is called on it."""

    def __init__(self, model: type[TModel]) -> None:
        self.model = model
        self.criteria: list[ColumnElement[bool]] = []
        self.joins: list[Any] = []
        self.options: list[ExecutableOption] = []
        # noinspection PyTypeHints
        self.order_by: list[ColumnExpressionArgument[Any]] = [] 
        self.limit: int | None = None
        self.offset: int | None = None
        self.for_update: bool = False

    def where(self, *criteria: ColumnElement[bool]) -> Self:
        self.criteria.extend(criteria)
        return self

    def join(self, *targets: Any) -> Self:
        self.joins.extend(targets)
        return self

    def include(self, *options: ExecutableOption) -> Self:
        self.options.extend(options)
        return self

    def order(self, *columns: ColumnExpressionArgument[Any]) -> Self:
        self.order_by.extend(columns)
        return self

    def page(self, page: int, size: int) -> Self:
        self.offset, self.limit = (page - 1) * size, size
        return self

    def lock(self) -> Self:
        """SELECT ... FOR UPDATE — for any aggregate loaded to be modified."""
        self.for_update = True
        return self
