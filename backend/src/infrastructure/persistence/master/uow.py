"""MasterDB unit of work — implements the ``MasterUnitOfWork`` port."""

from infrastructure.persistence.uow import SqlUnitOfWork
from infrastructure.types import MasterSession


class SqlMasterUnitOfWork(SqlUnitOfWork):
    def __init__(self, session: MasterSession) -> None:
        super().__init__(session)
