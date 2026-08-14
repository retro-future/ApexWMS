"""Undoing a scan (§8's ``DELETE /receipts/{id}/scan/{imei}``).

Only while the receipt is a draft. Nothing here needs compensating,
because nothing has been posted: a scan on a draft is a row on a shopping
list, and the handset does not exist in stock until the receipt is
confirmed.
"""

from uuid import UUID

from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import GoodsReceiptRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.value_objects import IMEI


class UnscanReceiptUnitCommand(Command[Result]):
    # No body: both values name what to remove and come straight off the
    # URL, built by the router with no request model in between.
    goods_receipt_id: UUID
    imei: str


class UnscanReceiptUnitHandler(IRequestHandler[Result, UnscanReceiptUnitCommand]):
    def __init__(
        self,
        receipts: GoodsReceiptRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._receipts = receipts
        self._loader = loader
        self._uow = uow

    async def handle(self, request: UnscanReceiptUnitCommand) -> Result:
        receipt = await self._loader.load_receipt(request.goods_receipt_id)
        receipt.assert_editable()

        wanted = IMEI.parse(request.imei)
        for line in receipt.lines:
            found = next((u for u in line.units if u.imei == wanted), None)
            if found is None:
                continue
            line.units.remove(found)
            await self._receipts.remove_unit(found.id)
            await self._uow.commit()
            return Result.succeed(f"{wanted} removed from {receipt.number}")

        raise NotFoundError(f"{receipt.number} has no scan of IMEI {wanted}")
