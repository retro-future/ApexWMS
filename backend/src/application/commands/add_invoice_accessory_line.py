"""FR-4.2: add an accessory to a draft invoice by picking it from the catalog.

The till scans a barcode; away from a scanner, or for an accessory with no
printed barcode, the same line is added by product id and quantity. A phone
is refused here — a sale is of one named handset, added by its IMEI. The
resolved price is returned for the counter to read, exactly as a scan does;
nothing is priced until confirm (FR-4.5b1).
"""

from uuid import UUID

from pydantic import Field

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import InvoiceScanResultData
from application.ports import TenantUnitOfWork
from application.services import AccessoryLineWriter
from application.specs import SalesInvoiceForWrite
from domain.entities import Product, SalesInvoice
from infrastructure.persistence.tenant.models import ProductModel, SalesInvoiceModel


class AddInvoiceAccessoryLineCommandPayload(CamelModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=999)


class AddInvoiceAccessoryLineCommand(
    AddInvoiceAccessoryLineCommandPayload,
    Command[ResultWithData[InvoiceScanResultData]],
):
    # A URL path segment, filled in by the router — never sent by the client.
    sales_invoice_id: UUID


class AddInvoiceAccessoryLineHandler(
    IRequestHandler[
        ResultWithData[InvoiceScanResultData], AddInvoiceAccessoryLineCommand
    ]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        products: TenantDbRepository[Product, ProductModel],
        accessory: AccessoryLineWriter,
        uow: TenantUnitOfWork,
    ) -> None:
        self._invoices = invoices
        self._products = products
        self._accessory = accessory
        self._uow = uow

    async def handle(
        self, request: AddInvoiceAccessoryLineCommand
    ) -> ResultWithData[InvoiceScanResultData]:
        spec = SalesInvoiceForWrite(request.sales_invoice_id)
        invoice = await self._invoices.find_one(spec)
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store"
            )
        invoice.assert_editable()

        product = await self._products.get(request.product_id)
        if product is None:
            raise NotFoundError("no such product in this store")

        line, resolved = await self._accessory.add(invoice, product, request.quantity)
        await self._invoices.update(invoice, spec)
        await self._uow.commit()

        return ResultWithData[InvoiceScanResultData].succeed_with_data(
            InvoiceScanResultData.from_entity(invoice, line, resolved)
        )
