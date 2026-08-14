"""FR-3.4, FR-3.5: one beep of the scanner.

Everything here is shaped by §6's scanning contract. The operator is
holding the phone, so a bad IMEI is rejected **on the scan that caused
it**, not when a fifty-unit receipt is submitted:

- a malformed IMEI fails the Luhn check in ``IMEI.parse`` and never
  reaches a repository;
- an IMEI already in this store is refused with the existing unit's status
  and location, because a duplicate is either a mis-scan or a stolen-goods
  red flag;
- an identical repeat scan onto the same open receipt is a **no-op**, not
  an error — scanners double-fire, and punishing that would train the
  operator to ignore the screen.

Cost and asking price are optional on the body and require the pricing
permission at the route. A Storekeeper sends an IMEI and a condition and
nothing else (FR-3.4b); an Owner or Manager prices it, here or afterwards.
"""

from uuid import UUID, uuid4

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import DuplicateImeiError, NotFoundError
from application.models import ScanResultData
from application.ports import DeviceUnitRepository, GoodsReceiptRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.entities import GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.enums import DeviceCondition
from domain.errors import ReceiptIncompleteError
from domain.permissions import Permission
from domain.value_objects import IMEI, Currency, Money


class ScanReceiptUnitCommandPayload(CamelModel):
    # Raw scanner input: spaces and hyphens are tolerated, the Luhn check
    # digit is not optional.
    imei: str
    line_id: UUID | None = None
    imei2: str | None = None
    serial_number: str | None = None
    condition: DeviceCondition = DeviceCondition.NEW
    # --- pricing permission only (FR-3.4b) ---
    acquisition_cost: str | int | None = None
    asking_price: str | int | None = None
    cash_paid: str | int | None = None
    cash_paid_currency: Currency | None = None


class ScanReceiptUnitCommand(
    ScanReceiptUnitCommandPayload, Command[ResultWithData[ScanResultData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    goods_receipt_id: UUID


class ScanReceiptUnitHandler(
    IRequestHandler[ResultWithData[ScanResultData], ScanReceiptUnitCommand]
):
    def __init__(
        self,
        receipts: GoodsReceiptRepository,
        units: DeviceUnitRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._units = units
        self._loader = loader
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ScanReceiptUnitCommand
    ) -> ResultWithData[ScanResultData]:
        receipt = await self._loader.load_receipt(request.goods_receipt_id)
        receipt.assert_editable()

        imei = IMEI.parse(request.imei)
        line = self._target_line(receipt, request.line_id)

        already = next((u for u in receipt.units() if u.imei == imei), None)
        if already is not None:
            # A double-fire of the same trigger pull. Nothing changes and
            # the running count is returned as if the first scan had just
            # happened (§6).
            return self._result(already, line)

        existing = await self._units.get_by_imei(str(imei))
        if existing is not None:
            where = f" at location {existing.location_id}" if existing.location_id else ""
            raise DuplicateImeiError(
                f"IMEI {imei} is already in this store: {existing.status.value}{where} "
                "(FR-3.5)"
            )

        if len(line.units) >= line.quantity:
            raise ReceiptIncompleteError(
                f"line already holds {line.quantity} of {line.quantity} scanned "
                "handsets — raise the line quantity before scanning another"
            )

        unit = ReceivedUnit(
            id=uuid4(),
            goods_receipt_line_id=line.id,
            imei=imei,
            imei2=IMEI.parse(request.imei2) if request.imei2 else None,
            serial_number=request.serial_number,
            condition=request.condition,
            acquisition_cost=self._money(request.acquisition_cost, line.currency),
            asking_price=self._money(request.asking_price, line.currency),
            cash_paid_minor=self._cash_paid_minor(request),
            cash_paid_currency=request.cash_paid_currency,
        )
        line.units.append(unit)
        await self._receipts.add_unit(unit)
        await self._uow.commit()
        return self._result(unit, line)

    @staticmethod
    def _target_line(receipt: GoodsReceipt, line_id: UUID | None) -> GoodsReceiptLine:
        """Which line this handset belongs to.

        Naming the line is optional because the common receipt has exactly
        one serialized line and the operator should not have to say so
        fifty times.
        """
        serial_lines = [line for line in receipt.lines if line.is_serial]
        if line_id is not None:
            found = next((line for line in serial_lines if line.id == line_id), None)
            if found is None:
                raise NotFoundError(
                    f"{receipt.number} has no serialized line {line_id}"
                )
            return found
        if len(serial_lines) != 1:
            raise NotFoundError(
                f"{receipt.number} has {len(serial_lines)} serialized lines — "
                "the scan must name which one it belongs to"
            )
        return serial_lines[0]

    @staticmethod
    def _money(amount: str | int | None, currency: Currency) -> Money | None:
        """The currency is the product's, never the caller's (§4.5 rule 3)."""
        return None if amount is None else Money.from_major(amount, currency)

    @staticmethod
    def _cash_paid_minor(request: ScanReceiptUnitCommand) -> int | None:
        """The som actually handed over, as a bare amount (§4.5b).

        Parsed through ``Money`` for the exactness, then unwrapped, because
        this figure must not be a ``Money`` on the entity: it enters no
        ledger and no total, and the whole point is that it cannot join
        one (FR-3.4d).
        """
        if request.cash_paid is None or request.cash_paid_currency is None:
            return None
        return Money.from_major(request.cash_paid, request.cash_paid_currency).amount_minor

    def _result(
        self, unit: ReceivedUnit, line: GoodsReceiptLine
    ) -> ResultWithData[ScanResultData]:
        return ResultWithData[ScanResultData].succeed_with_data(
            ScanResultData.from_entity(
                unit, line, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
