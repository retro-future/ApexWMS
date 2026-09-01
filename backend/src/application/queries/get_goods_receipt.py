"""One Goods Receipt, shaped to what the reader may see.

A Storekeeper reads this constantly while scanning, and gets the lines,
the running counts, each handset's condition and its asking price —
including which units still have none, which is what FR-3.10 will refuse
the confirm over. Costs and the som handed over need
``Permission.Cost.View`` and are simply absent otherwise (FR-1.7).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import GoodsReceiptData
from application.specs import GoodsReceiptById
from domain.entities import GoodsReceipt
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import GoodsReceiptModel


class GetGoodsReceiptQuery(Query[ResultWithData[GoodsReceiptData]]):
    goods_receipt_id: UUID


class GetGoodsReceiptHandler(
    IRequestHandler[ResultWithData[GoodsReceiptData], GetGoodsReceiptQuery]
):
    def __init__(
        self,
        receipts: TenantDbRepository[GoodsReceipt, GoodsReceiptModel],
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._current = current

    async def handle(
        self, request: GetGoodsReceiptQuery
    ) -> ResultWithData[GoodsReceiptData]:
        receipt = await self._receipts.find_one(GoodsReceiptById(request.goods_receipt_id))
        if receipt is None:
            raise NotFoundError(
                f"goods receipt {request.goods_receipt_id} does not exist in this store",
                key="not_found",
                subject_key="goods_receipt",
            )
        return ResultWithData[GoodsReceiptData].succeed_with_data(
            GoodsReceiptData.from_entity(
                receipt, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
