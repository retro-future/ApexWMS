"""``Command``/``Query`` bases — plain ``IRequest`` subclasses that pick up
the camelCase wire convention via ``CamelModel``, with no repeated
``model_config``.

Ported from the reference ``Command``/``Query`` classes (med-image-scanner)
and ``PagedRequest`` (xterminal). Two bugs were found and fixed:

1. The reference ``Command``/``Query`` were declared as
   ``class Command(BaseModel, IRequest[TResult])`` where ``IRequest``
   already extends ``BaseModel`` — a diamond with ``BaseModel`` listed
   *before* its own subclass, which is a textbook C3 MRO failure
   (``TypeError: Cannot create a consistent method resolution order``).
   Fixed by putting the camelCase mixin after ``IRequest[TResult]`` in
   the bases instead of duplicating ``BaseModel`` before it.
2. ``PagedRequest.page``/``page_size`` had no lower-bound validation, so
   ``page_size=0`` would reach ``PagedResult.succeed_with_data``'s
   ``ceil(items_count / page_size)`` and raise ``ZeroDivisionError``.
   Fixed with ``Field(ge=1)`` at the source rather than guarding the
   division downstream.
"""

from pydantic import Field

from application.core.model import CamelModel
from application.core.request import IRequest
from application.core.results import PagedResult, Result


class Command[TResult: Result](IRequest[TResult], CamelModel):
    pass


class Query[TResult: Result](IRequest[TResult], CamelModel):
    pass


class PagedQuery[TResult: PagedResult](Query[TResult]):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    order_by: str | None = None
