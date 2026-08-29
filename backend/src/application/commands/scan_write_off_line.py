"""FR-6.5: one beep onto an open write-off.

The twin of ``scan_supplier_return_line``, against its own document. Both
delegate every question about the scanned string to ``RemovalScanner``,
including §6's refusal of a handset that is not on the shelf — a phone
already sold cannot also be written off, and finding that out at confirm
would mean carrying a broken document around the stockroom.
"""

from uuid import UUID, uuid4

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import WriteOffData
from application.ports import TenantUnitOfWork
from application.services import RemovalScanner
from application.specs import WriteOffForWrite
from domain.entities import WriteOff, WriteOffLine
from infrastructure.persistence.tenant.models import WriteOffModel


class ScanWriteOffLineCommandPayload(CamelModel):
    # Raw scanner input: an IMEI, a barcode or a SKU (§6, FR-7.1).
    code: str


class ScanWriteOffLineCommand(
    ScanWriteOffLineCommandPayload, Command[ResultWithData[WriteOffData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    write_off_id: UUID


class ScanWriteOffLineHandler(
    IRequestHandler[ResultWithData[WriteOffData], ScanWriteOffLineCommand]
):
    def __init__(
        self,
        write_offs: TenantDbRepository[WriteOff, WriteOffModel],
        scanner: RemovalScanner,
        uow: TenantUnitOfWork,
    ) -> None:
        self._write_offs = write_offs
        self._scanner = scanner
        self._uow = uow

    async def handle(
        self, request: ScanWriteOffLineCommand
    ) -> ResultWithData[WriteOffData]:
        spec = WriteOffForWrite(request.write_off_id)
        document = await self._write_offs.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"write-off {request.write_off_id} does not exist in this store"
            )
        document.assert_editable()

        product, unit = await self._scanner.resolve(
            request.code,
            location_id=document.location_id,
            number=document.number,
            # A write-off sends goods nowhere, so nothing has an origin to
            # match against (FR-5.2b).
            supplier_id=None,
        )

        if unit is not None:
            if document.line_for_unit(unit.id) is not None:
                # A double-fire of the same trigger pull (§6).
                return self._result(document)
            document.lines.append(
                WriteOffLine(
                    id=uuid4(),
                    write_off_id=document.id,
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
            # Three broken cases are three items, so a repeat barcode
            # increments rather than doing nothing.
            existing.quantity += 1
            return await self._save(document, spec)

        document.lines.append(
            WriteOffLine(
                id=uuid4(),
                write_off_id=document.id,
                product_id=product.id,
                quantity=1,
                currency=product.currency,
                tracking_type=product.tracking_type,
            )
        )
        return await self._save(document, spec)

    async def _save(
        self, document: WriteOff, spec: WriteOffForWrite
    ) -> ResultWithData[WriteOffData]:
        await self._write_offs.update(document, spec)
        await self._uow.commit()
        return self._result(document)

    @staticmethod
    def _result(document: WriteOff) -> ResultWithData[WriteOffData]:
        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
