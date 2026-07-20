"""TenantDB transaction boundary."""

from typing import Protocol

from application.ports.uow import UnitOfWork


class TenantUnitOfWork(UnitOfWork, Protocol):
    """Commits one tenant's database — never hand this to a use case touching MasterDB."""
