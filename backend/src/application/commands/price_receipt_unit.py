"""FR-3.4b: an Owner or Manager prices a handset the Storekeeper scanned.

This route is the workflow the permission split implies. A Storekeeper may
receive goods but may not see costs or set prices (§2.1), so on a delivery
containing used stock the two acts genuinely belong to two people: the
storekeeper scans fifty IMEIs, the owner walks the list and states what
each one cost and what it will be offered at.

Nothing is written to ``device_unit_price_changes`` here. The handset does
not exist yet — it is a row on a draft — and its price log begins at the
moment the receipt is confirmed and the unit is created (FR-3.11).
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import ReceivedUnitData
from application.ports import GoodsReceiptRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.entities import GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.enums import DeviceCondition
from domain.permissions import Permission
from domain.value_objects import IMEI, Currency, Money


class PriceReceiptUnitCommandPayload(CamelModel):
    acquisition_cost: str | int | None = None
    asking_price: str | int | None = None
    condition: DeviceCondition | None = None
    cash_paid: str | int | None = None
    cash_paid_currency: Currency | None = None


class PriceReceiptUnitCommand(
    PriceReceiptUnitCommandPayload, Command[ResultWithData[ReceivedUnitData]]
):
    # URL path segments, filled in by the router — never sent by the client.
    goods_receipt_id: UUID
    imei: str


class PriceReceiptUnitHandler(
    IRequestHandler[ResultWithData[ReceivedUnitData], PriceReceiptUnitCommand]
):
    def __init__(
        self,
        receipts: GoodsReceiptRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._loader = loader
        self._uow = uow
        self._current = current

    async def handle(
        self, request: PriceReceiptUnitCommand
    ) -> ResultWithData[ReceivedUnitData]:
        receipt = await self._loader.load_receipt(request.goods_receipt_id)
        receipt.assert_editable()

        line, unit = self._find(receipt, request.imei)

        if "acquisition_cost" in request.model_fields_set:
            unit.acquisition_cost = (
                None
                if request.acquisition_cost is None
                else Money.from_major(request.acquisition_cost, line.currency)
            )
        if "asking_price" in request.model_fields_set:
            unit.asking_price = (
                None
                if request.asking_price is None
                else Money.from_major(request.asking_price, line.currency)
            )
        if request.condition is not None:
            unit.condition = request.condition
        if "cash_paid" in request.model_fields_set:
            unit.cash_paid_minor = (
                None
                if request.cash_paid is None or request.cash_paid_currency is None
                else Money.from_major(
                    request.cash_paid, request.cash_paid_currency
                ).amount_minor
            )
            unit.cash_paid_currency = request.cash_paid_currency

        # Re-run the invariants over the edited row: a negative amount or a
        # half-stated cash_paid pair must fail here, not at the column.
        unit.__post_init__()
        await self._receipts.update_unit(unit)
        await self._uow.commit()

        return ResultWithData[ReceivedUnitData].succeed_with_data(
            ReceivedUnitData.from_entity(
                unit, line, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )

    @staticmethod
    def _find(
        receipt: GoodsReceipt, imei: str
    ) -> tuple[GoodsReceiptLine, ReceivedUnit]:
        """The scan and the line it sits on — the line carries the currency."""
        wanted = IMEI.parse(imei)
        for line in receipt.lines:
            for unit in line.units:
                if unit.imei == wanted:
                    return line, unit
        raise NotFoundError(f"{receipt.number} has no scan of IMEI {wanted}")
