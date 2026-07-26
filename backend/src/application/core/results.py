"""The envelope a handler returns on its success path.

Failure is *not* represented here for the HTTP path — handlers raise the
existing ``ApplicationError``/``DomainError`` subclasses exactly as
today's use cases do, and ``presentation/errors.py`` maps them to a
status code, unchanged. ``fail()`` stays defined for general-purpose use
(e.g. a CLI-only caller that wants an envelope instead of a raise), but
no router or handler in this codebase is required to call it.

Ported from the reference ``Result``/``ResultWithData``/``PagedResult``
classes. Two bugs were found and fixed while porting:

1. ``succeed_with_data``/``fail`` were ``@staticmethod``s that
   re-referenced the class's own *unparametrized* generic name inside
   their own body (e.g. ``ResultWithData[TData](...)``). Calling them
   through a parametrized alias like ``ResultWithData[Payload].fail(...)``
   never binds ``TData`` to ``Payload`` in that reference — pydantic
   treats the field as effectively unvalidated, so
   ``ResultWithData[Payload].succeed_with_data(some_garbage_dict)``
   silently succeeds instead of raising. Converting to ``@classmethod``
   and constructing via ``cls(...)`` fixes this: ``cls`` is the actual
   parametrized class the caller invoked through.
2. ``ResultWithData.data`` was a required field with no default, which
   made ``fail()`` impossible to construct without a dummy payload.
   Made ``TData | None = None``.
"""

from math import ceil
from typing import Self

from application.core.model import CamelModel


class Result(CamelModel):
    success: bool
    message: str | None = None
    error: str | None = None

    @classmethod
    def succeed(cls, message: str | None = None) -> Self:
        return cls(success=True, message=message)

    @classmethod
    def fail(cls, error: str | None = None) -> Self:
        return cls(success=False, error=error or "An error occurred")


class ResultWithData[TData](Result):
    data: TData | None = None

    @classmethod
    def succeed_with_data(cls, payload: TData) -> Self:
        return cls(success=True, data=payload)

    @classmethod
    def fail(cls, error: str | None = None) -> Self:
        return cls(success=False, data=None, error=error or "An error occurred")


class PagedResult[TData](Result):
    data: list[TData] = []
    page_index: int = 0
    page_size: int = 0
    pages_count: int = 0
    total_items: int = 0

    @classmethod
    def succeed_with_data(
        cls,
        data: list[TData],
        page_index: int,
        page_size: int,
        items_count: int,
    ) -> Self:
        return cls(
            success=True,
            data=data,
            page_index=page_index,
            page_size=page_size,
            pages_count=ceil(items_count / page_size),
            total_items=items_count,
        )

    @classmethod
    def fail(cls, error: str | None = None) -> Self:
        return cls(success=False, error=error or "An error occurred")
