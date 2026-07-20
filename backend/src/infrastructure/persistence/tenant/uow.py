"""TenantDB unit of work — implements the ``TenantUnitOfWork`` port."""

from infrastructure.persistence.uow import SqlUnitOfWork
from infrastructure.types import TenantSession


class SqlTenantUnitOfWork(SqlUnitOfWork):
    def __init__(self, session: TenantSession) -> None:
        super().__init__(session)
