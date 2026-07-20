"""MasterDB transaction boundary."""

from typing import Protocol

from application.ports.uow import UnitOfWork


class MasterUnitOfWork(UnitOfWork, Protocol):
    """Commits MasterDB work — never hand this to a use case touching TenantDB."""
