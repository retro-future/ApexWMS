"""One Goods Receipt, shaped to what the reader may see.

A Storekeeper reads this constantly while scanning, and gets the lines,
the running counts, each handset's condition and its asking price —
including which units still have none, which is what FR-3.10 will refuse
the confirm over. Costs and the som handed over need
``Permission.Cost.View`` and are simply absent otherwise (FR-1.7).
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.models import GoodsReceiptData
from application.services import DocumentLoader
from domain.permissions import Permission


class GetGoodsReceiptQuery(Query[ResultWithData[GoodsReceiptData]]):
    goods_receipt_id: UUID


class GetGoodsReceiptHandler(
    IRequestHandler[ResultWithData[GoodsReceiptData], GetGoodsReceiptQuery]
):
    def __init__(self, loader: DocumentLoader, current: CurrentUser) -> None:
        self._loader = loader
        self._current = current

    async def handle(
        self, request: GetGoodsReceiptQuery
    ) -> ResultWithData[GoodsReceiptData]:
        receipt = await self._loader.load_receipt(request.goods_receipt_id)
        return ResultWithData[GoodsReceiptData].succeed_with_data(
            GoodsReceiptData.from_entity(
                receipt, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
