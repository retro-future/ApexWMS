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

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import SupplierReturnData
from application.ports import TenantUnitOfWork
from application.services import RemovalScanner
from application.specs import SupplierReturnForWrite
from domain.entities import SupplierReturn, SupplierReturnLine
from infrastructure.persistence.tenant.models import SupplierReturnModel


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
        returns: TenantDbRepository[SupplierReturn, SupplierReturnModel],
        scanner: RemovalScanner,
        uow: TenantUnitOfWork,
    ) -> None:
        self._returns = returns
        self._scanner = scanner
        self._uow = uow

    async def handle(
        self, request: ScanSupplierReturnLineCommand
    ) -> ResultWithData[SupplierReturnData]:
        spec = SupplierReturnForWrite(request.supplier_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"supplier return {request.supplier_return_id} does not exist in this store",
                key="not_found",
                subject_key="supplier_return",
            )
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
            document.lines.append(
                SupplierReturnLine(
                    id=uuid4(),
                    supplier_return_id=document.id,
                    product_id=product.id,
                    device_unit_id=unit.id,
                    imei=unit.imei.value,
                    quantity=1,
                    currency=product.currency,
                    tracking_type=product.tracking_type,
                )
            )
            return await self._save(document, spec)

        existing = document.line_for_product(product.id)
        if existing is not None:
            existing.quantity += 1
            return await self._save(document, spec)

        document.lines.append(
            SupplierReturnLine(
                id=uuid4(),
                supplier_return_id=document.id,
                product_id=product.id,
                quantity=1,
                currency=product.currency,
                tracking_type=product.tracking_type,
            )
        )
        return await self._save(document, spec)

    async def _save(
        self, document: SupplierReturn, spec: SupplierReturnForWrite
    ) -> ResultWithData[SupplierReturnData]:
        await self._returns.update(document, spec)
        await self._uow.commit()
        return self._result(document)

    @staticmethod
    def _result(document: SupplierReturn) -> ResultWithData[SupplierReturnData]:
        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )
