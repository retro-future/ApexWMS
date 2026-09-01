"""Cancelling a confirmed return to a supplier (§4.4, FR-10.2).

**Compensation, never deletion.** The ``−`` movements and the
``SUPPLIER_RETURN_CREDIT`` entries stay exactly where they are, and
``LedgerPoster.reverse`` appends their negation. The handsets are
reprojected from their own timelines, which walks each one back from
``RETURNED_TO_SUPPLIER`` to ``IN_STOCK`` at the location it left from.

``SupplierReturn.cancel`` is what stops this running twice: reversing a
reversal would re-apply the return, and the poster deliberately holds no
guard of its own.

What this does *not* do is tell the supplier. A return called off after the
box has shipped is a conversation, and the ledger's job is only to stop
claiming the goods left.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SupplierReturnData
from application.ports import Clock, TenantUnitOfWork
from application.services import LedgerPoster
from application.specs import SupplierReturnForWrite
from domain.entities import SupplierReturn
from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import SupplierReturnModel


class CancelSupplierReturnCommandPayload(CamelModel):
    reason: str | None = None


class CancelSupplierReturnCommand(
    CancelSupplierReturnCommandPayload, Command[ResultWithData[SupplierReturnData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    supplier_return_id: UUID


class CancelSupplierReturnHandler(
    IRequestHandler[ResultWithData[SupplierReturnData], CancelSupplierReturnCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[SupplierReturn, SupplierReturnModel],
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._returns = returns
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelSupplierReturnCommand
    ) -> ResultWithData[SupplierReturnData]:
        spec = SupplierReturnForWrite(request.supplier_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"supplier return {request.supplier_return_id} does not exist in this store",
                key="not_found",
                subject_key="supplier_return",
            )

        document.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.SUPPLIER_RETURN, document.id)
        await self._returns.update(document, spec)
        await self._uow.commit()

        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )
