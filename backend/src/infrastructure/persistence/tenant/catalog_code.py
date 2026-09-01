"""Handing out the next generated SKU / barcode number (see ``document_number.py``).

Same ``SELECT ... FOR UPDATE`` counter as the document numberer, and for
the same reason: a locked row rolls back with the caller's transaction, so
a discarded product create does not burn a number and the sequence stays
dense. No year here: a catalog code never restarts.
"""

from sqlalchemy import select

from domain.enums import CatalogCodeKind
from infrastructure.persistence.tenant.models import CatalogCodeSequenceModel
from infrastructure.types import TenantSession


class SqlCatalogCodeAllocator:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def next(self, kind: CatalogCodeKind) -> int:
        row = await self._session.scalar(
            select(CatalogCodeSequenceModel)
            .where(CatalogCodeSequenceModel.kind == kind.value)
            .with_for_update()
        )
        if row is None:
            self._session.add(
                CatalogCodeSequenceModel(kind=kind.value, last_number=1)
            )
            await self._session.flush()
            return 1

        row.last_number += 1
        return row.last_number
