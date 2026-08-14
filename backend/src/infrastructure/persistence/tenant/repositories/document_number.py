"""Handing out the next document number (PRD §4.4).

``SELECT ... FOR UPDATE`` rather than a Postgres sequence, for one reason:
a sequence is transaction-independent, so a rolled-back draft would burn
its number and the year's receipts would come out as 1, 2, 4, 7. A locked
counter row rolls back with everything else, so the run stays dense and a
gap means something happened.

The lock is held to the end of the caller's transaction, which is short —
one insert away — and serializes only operators opening a document of the
same type in the same year.
"""

from sqlalchemy import select

from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import DocumentSequenceModel

from .base import TenantRepository


class SqlDocumentNumberRepository(TenantRepository):
    async def next_number(self, document_type: DocumentType, year: int) -> int:
        row = await self._session.scalar(
            select(DocumentSequenceModel)
            .where(
                DocumentSequenceModel.document_type == document_type.value,
                DocumentSequenceModel.year == year,
            )
            .with_for_update()
        )
        if row is None:
            # First document of this type this year. A concurrent insert of
            # the same key loses on the primary key rather than duplicating
            # a number.
            await self._insert(
                DocumentSequenceModel(
                    document_type=document_type.value, year=year, last_number=1
                )
            )
            return 1

        row.last_number += 1
        return row.last_number
