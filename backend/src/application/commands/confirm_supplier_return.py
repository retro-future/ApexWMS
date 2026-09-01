"""FR-5.3: confirming a return, and the first writer of ``SUPPLIER_RETURN_CREDIT``.

The same shape as ``ConfirmGoodsReceiptHandler``, and for the same reason:
the handler decides nothing about returning goods. It asks the aggregate
whether the return may be confirmed, asks ``RemovalPoster`` to take the
goods off the shelf at their book value, and owns the transaction both
ledgers are written inside (FR-10.1).

A handset sold from under the draft is discovered here rather than at the
scan, because a draft reserves nothing — and it rolls the whole return back
rather than sending nine phones and quietly dropping the tenth.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SupplierReturnData
from application.ports import Clock, TenantUnitOfWork
from application.services import RemovalPoster
from application.specs import SupplierReturnForWrite
from domain.entities import SupplierReturn
from infrastructure.persistence.tenant.models import SupplierReturnModel


class ConfirmSupplierReturnCommand(Command[ResultWithData[SupplierReturnData]]):
    # No body: this action needs nothing beyond the return in the URL. The
    # router builds this straight from the path.
    supplier_return_id: UUID


class ConfirmSupplierReturnHandler(
    IRequestHandler[ResultWithData[SupplierReturnData], ConfirmSupplierReturnCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[SupplierReturn, SupplierReturnModel],
        poster: RemovalPoster,
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
        self, request: ConfirmSupplierReturnCommand
    ) -> ResultWithData[SupplierReturnData]:
        spec = SupplierReturnForWrite(request.supplier_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"supplier return {request.supplier_return_id} does not exist in this store",
                key="not_found",
                subject_key="supplier_return",
            )

        document.confirm(self._clock.now(), self._current.user_id)
        await self._poster.send_back(document)
        await self._returns.update(document, spec)
        await self._uow.commit()

        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )
