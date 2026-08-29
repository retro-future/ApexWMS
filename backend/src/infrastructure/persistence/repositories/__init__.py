"""The repository generics (ADR 0007): one database-agnostic pair, and a
per-database narrowing of each.

- ``base.py`` — ``SqlAppendOnlyRepository`` / ``SqlAlchemyRepository``
- ``tenant.py`` — the same two bound to ``TenantSession``
- ``master.py`` — ``SqlAlchemyRepository`` bound to ``MasterSession``
"""

from infrastructure.persistence.repositories.base import (
    SqlAlchemyRepository,
    SqlAppendOnlyRepository,
)
from infrastructure.persistence.repositories.master import MasterSqlRepository
from infrastructure.persistence.repositories.tenant import (
    TenantSqlAppendOnlyRepository,
    TenantSqlRepository,
)

__all__ = [
    "MasterSqlRepository",
    "SqlAlchemyRepository",
    "SqlAppendOnlyRepository",
    "TenantSqlAppendOnlyRepository",
    "TenantSqlRepository",
]
