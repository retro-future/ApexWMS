"""``IRequestHandler``: one handler, contravariant in its request, covariant
in its result.

Ported from the reference ``IRequestHandler`` (xterminal), which bound
``TReq_contra`` to raw ``IRequest`` with no link to the handler's own result
type. Tying them together by writing ``bound=IRequest[TRes_co]`` doesn't
type-check — a ``TypeVar``'s ``bound=`` must be a concrete type, not another
type variable (pyright: "Constraints cannot be parametrized by type
variables" / "Unbound type variable"), and a stray module-level ``TRes`` left
over from that attempt was never itself used ("Type parameter 'TRes' is not
used"). The bound is relaxed to ``IRequest[Any]``; the result/request
coupling is instead enforced by convention — every concrete
``Command``/``Query`` already declares its own result via
``IRequest[TResult]`` (``application/core/cqrs.py``), and each
``SomeHandler(IRequestHandler[TRes, TReq])`` is written by hand to match.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from application.core.request import IRequest

TRes_co = TypeVar("TRes_co", covariant=True)
TReq_contra = TypeVar("TReq_contra", bound=IRequest[Any], contravariant=True)


class IRequestHandler(Generic[TRes_co, TReq_contra], ABC):  # noqa: UP046 -- explicit TypeVar variance requested over PEP 695 params
    @abstractmethod
    async def handle(self, request: TReq_contra) -> TRes_co: ...
