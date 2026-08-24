"""FR-6.5: one beep onto an open write-off.

The twin of ``scan_supplier_return_line``, against its own document. Both
delegate every question about the scanned string to ``RemovalScanner``,
including §6's refusal of a handset that is not on the shelf — a phone
already sold cannot also be written off, and finding that out at confirm
would mean carrying a broken document around the stockroom.
"""

from uuid import UUID, uuid4

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.models import WriteOffData
from application.ports import TenantUnitOfWork, WriteOffRepository
from application.services import DocumentLoader, RemovalScanner
from domain.entities import WriteOff, WriteOffLine


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
        write_offs: WriteOffRepository,
        scanner: RemovalScanner,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._write_offs = write_offs
        self._scanner = scanner
        self._loader = loader
        self._uow = uow

    async def handle(
        self, request: ScanWriteOffLineCommand
    ) -> ResultWithData[WriteOffData]:
        document = await self._loader.load_write_off(request.write_off_id)
        document.assert_editable()

        product, unit = await self._scanner.resolve(
            request.code, location_id=document.location_id, number=document.number
        )

        if unit is not None:
            if document.line_for_unit(unit.id) is not None:
                # A double-fire of the same trigger pull (§6).
                return self._result(document)
            await self._append(
                document,
                WriteOffLine(
                    id=uuid4(),
                    write_off_id=document.id,
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
            # Three broken cases are three items, so a repeat barcode
            # increments rather than doing nothing.
            existing.quantity += 1
            await self._write_offs.update_line(existing)
            await self._uow.commit()
            return self._result(document)

        await self._append(
            document,
            WriteOffLine(
                id=uuid4(),
                write_off_id=document.id,
                product_id=product.id,
                quantity=1,
                currency=product.currency,
                tracking_type=product.tracking_type,
            ),
        )
        return self._result(document)

    async def _append(self, document: WriteOff, line: WriteOffLine) -> None:
        document.lines.append(line)
        await self._write_offs.add_line(line)
        await self._uow.commit()

    @staticmethod
    def _result(document: WriteOff) -> ResultWithData[WriteOffData]:
        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
