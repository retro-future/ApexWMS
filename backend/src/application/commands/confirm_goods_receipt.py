"""FR-3.7: confirming a Goods Receipt, and the first real caller of both ledgers.

The shape PRD §7.4 traces end to end. The handler decides nothing about
receiving: it asks the aggregate whether the receipt may be confirmed
(FR-3.8, FR-3.10, and every rule in ``GoodsReceipt.confirm``), asks
``ReceiptPoster`` to turn it into stock, and owns the transaction the two
ledgers are written inside.

That last part is the whole point of the split. ``LedgerPoster`` never
commits, so goods and money land together or not at all (FR-10.1) — a
duplicate IMEI discovered on the tenth handset rolls back the nine before
it, and there is no state where the stock moved and the money did not.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import GoodsReceiptData
from application.ports import Clock, TenantUnitOfWork
from application.services import ReceiptPoster
from application.specs import GoodsReceiptForWrite
from domain.entities import GoodsReceipt
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import GoodsReceiptModel


class ConfirmGoodsReceiptCommand(Command[ResultWithData[GoodsReceiptData]]):
    # No body: this action needs nothing beyond the receipt in the URL. The
    # router builds this straight from the path, with no request model in
    # between.
    goods_receipt_id: UUID


class ConfirmGoodsReceiptHandler(
    IRequestHandler[ResultWithData[GoodsReceiptData], ConfirmGoodsReceiptCommand]
):
    def __init__(
        self,
        receipts: TenantDbRepository[GoodsReceipt, GoodsReceiptModel],
        poster: ReceiptPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ConfirmGoodsReceiptCommand
    ) -> ResultWithData[GoodsReceiptData]:
        spec = GoodsReceiptForWrite(request.goods_receipt_id)
        receipt = await self._receipts.find_one(spec)
        if receipt is None:
            raise NotFoundError(
                f"goods receipt {request.goods_receipt_id} does not exist in this store"
            )

        receipt.confirm(self._clock.now(), self._current.user_id)
        await self._poster.receive(receipt)
        await self._receipts.update(receipt, spec)
        await self._uow.commit()

        return ResultWithData[GoodsReceiptData].succeed_with_data(
            GoodsReceiptData.from_entity(
                receipt, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
