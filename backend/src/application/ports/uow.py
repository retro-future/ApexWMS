"""The transaction-boundary port.

The master/tenant variants live in ``master/uow.py`` and
``tenant/uow.py`` — two distinct ports because two distinct databases
exist (PRD §3.1), and the DI container keys on the type.
"""

from typing import Protocol


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
