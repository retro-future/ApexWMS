"""``IRequest``: marker for one message that flows through exactly one handler.

Ported from the reference ``IRequest`` (xterminal). ``TRes`` is a phantom
marker parameter — never referenced in the class body itself — that exists
only so a concrete ``Command``/``Query`` subclass can pin its own result type
(``LoginCommand(IRequest[LoginResult])``) for
:class:`application.core.handler.IRequestHandler` to pick up. Declared with
an explicit ``TypeVar``/``Generic`` rather than PEP 695 type-parameter syntax
so type checkers don't flag ``TRes`` as an unused type parameter.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

TRes = TypeVar("TRes")


class IRequest(BaseModel, Generic[TRes]):  # noqa: UP046 -- explicit TypeVar requested over PEP 695 params
    """Marker for one message that flows through exactly one handler."""
