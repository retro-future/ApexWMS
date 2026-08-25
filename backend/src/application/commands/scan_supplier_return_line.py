"""FR-5.1, FR-5.2: one beep onto an open supplier return.

One endpoint, two possible answers, exactly as §6's contract says: the
client sends a string and the server decides whether it named a handset or
a catalog row. ``RemovalScanner`` asks every question both removal
documents ask; what is left here is building the line.

A repeat **IMEI** is a no-op — one phone, one line, and a double-fired
trigger must not be punished. A repeat **barcode** increments, because
three damaged cases going back are three items, which is the same
departure ``scan_invoice_line`` makes and for the same reason.
"""

from uuid import UUID, uuid4

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.models import SupplierReturnData
from application.ports import SupplierReturnRepository, TenantUnitOfWork
from application.services import DocumentLoader, RemovalScanner
from domain.entities import SupplierReturn, SupplierReturnLine


class ScanSupplierReturnLineCommandPayload(CamelModel):
    # Raw scanner input: an IMEI, a barcode or a SKU. The client does not
    # have to guess which (§6, FR-7.1).
    code: str


class ScanSupplierReturnLineCommand(
    ScanSupplierReturnLineCommandPayload, Command[ResultWithData[SupplierReturnData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    supplier_return_id: UUID


class ScanSupplierReturnLineHandler(
    IRequestHandler[ResultWithData[SupplierReturnData], ScanSupplierReturnLineCommand]
):
    def __init__(
        self,
        returns: SupplierReturnRepository,
        scanner: RemovalScanner,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._returns = returns
        self._scanner = scanner
        self._loader = loader
        self._uow = uow

    async def handle(
        self, request: ScanSupplierReturnLineCommand
    ) -> ResultWithData[SupplierReturnData]:
        document = await self._loader.load_return(request.supplier_return_id)
        document.assert_editable()

        product, unit = await self._scanner.resolve(
            request.code,
            location_id=document.location_id,
            number=document.number,
            supplier_id=document.supplier_id,
        )

        if unit is not None:
            if document.line_for_unit(unit.id) is not None:
                # A double-fire of the same trigger pull (§6).
                return self._result(document)
            await self._append(
                document,
                SupplierReturnLine(
                    id=uuid4(),
                    supplier_return_id=document.id,
                    product_id=product.id,
                    device_unit_id=unit.id,
                    imei=unit.imei.value,
                    quantity=1,
                    currency=product.currency,
                    tracking_type=product.tracking_type,
                ),
            )
            return self._result(document)

        existing = document.line_for_product(product.id)
        if existing is not None:
            existing.quantity += 1
            await self._returns.update_line(existing)
            await self._uow.commit()
            return self._result(document)

        await self._append(
            document,
            SupplierReturnLine(
                id=uuid4(),
                supplier_return_id=document.id,
                product_id=product.id,
                quantity=1,
                currency=product.currency,
                tracking_type=product.tracking_type,
            ),
        )
        return self._result(document)

    async def _append(
        self, document: SupplierReturn, line: SupplierReturnLine
    ) -> None:
        document.lines.append(line)
        await self._returns.add_line(line)
        await self._uow.commit()

    @staticmethod
    def _result(document: SupplierReturn) -> ResultWithData[SupplierReturnData]:
        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )
