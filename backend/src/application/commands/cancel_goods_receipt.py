"""Cancelling a confirmed Goods Receipt (§4.3 rule 2, §4.4, FR-10.2).

**Compensation, never deletion.** The movements and money entries the
receipt wrote stay exactly where they are, and ``LedgerPoster.reverse``
appends their negation. A cancelled receipt is therefore *two* sets of
rows, not zero: the history of the mistake is part of the history.

The handsets it brought in are reprojected from their own timelines, which
leaves them ``RECEIPT_CANCELLED`` — not written off. The store lost
nothing, and a write-off report that counted these would be reporting
losses that never happened.

``GoodsReceipt.cancel`` is what stops this running twice. Reversing a
reversal would re-apply the receipt, and the poster deliberately holds no
guard of its own — the document's state is the one place that knows.
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import GoodsReceiptData
from application.ports import Clock, GoodsReceiptRepository, TenantUnitOfWork
from application.services import DocumentLoader, LedgerPoster
from domain.enums import DocumentType
from domain.permissions import Permission


class CancelGoodsReceiptCommandPayload(CamelModel):
    reason: str | None = None


class CancelGoodsReceiptCommand(
    CancelGoodsReceiptCommandPayload, Command[ResultWithData[GoodsReceiptData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    goods_receipt_id: UUID


class CancelGoodsReceiptHandler(
    IRequestHandler[ResultWithData[GoodsReceiptData], CancelGoodsReceiptCommand]
):
    def __init__(
        self,
        receipts: GoodsReceiptRepository,
        loader: DocumentLoader,
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._loader = loader
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelGoodsReceiptCommand
    ) -> ResultWithData[GoodsReceiptData]:
        receipt = await self._loader.load_receipt(request.goods_receipt_id)

        receipt.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.GOODS_RECEIPT, receipt.id)
        await self._receipts.update(receipt)
        await self._uow.commit()

        return ResultWithData[GoodsReceiptData].succeed_with_data(
            GoodsReceiptData.from_entity(
                receipt, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
