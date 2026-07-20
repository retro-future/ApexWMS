"""The TenantDB repository base.

The constructor demands ``TenantSession`` — see ``master/repositories/base.py``
for the rationale. No CRUD aggregate lives tenant-side at M1; the first
subclasses arrive with the M2 catalog.
"""

from infrastructure.persistence.repository import CrudRepository
from infrastructure.types import TenantSession


class TenantCrudRepository[EntityT, KeyT, ModelT](CrudRepository[EntityT, KeyT, ModelT]):
    def __init__(self, session: TenantSession) -> None:
        super().__init__(session)
