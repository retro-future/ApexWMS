"""FR-4.9a, FR-4.9b: one beep onto an open customer return.

One endpoint, two possible answers, exactly as §6's contract says: the
client sends a string and the server decides whether it named a handset or
a catalog row. ``CustomerReturnScanner`` asks every question about the sale;
what is left here is building the line.

The refund a line starts at is the invoice line's own ``charged_price``, and
that is the whole of FR-4.9c's default. Lowering it is a separate, named act
with a separate permission, because keeping some of a customer's money is a
decision somebody makes rather than a number that arrives with a scan.

A repeat **IMEI** is a no-op — one phone, one line, and a double-fired
trigger must not be punished. A repeat **barcode** increments, up to what the
sale sold, which is the same departure ``scan_invoice_line`` makes.
"""

from uuid import UUID, uuid4

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import CustomerReturnData
from application.ports import TenantUnitOfWork
from application.services import CustomerReturnScanner
from application.specs import (
    CustomerReturnForWrite,
    CustomerReturnsForInvoice,
    SalesInvoiceById,
)
from domain.entities import (
    CustomerReturn,
    CustomerReturnLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from domain.errors import AlreadyReturnedError
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import (
    CustomerReturnModel,
    SalesInvoiceModel,
)


class ScanCustomerReturnLineCommandPayload(CamelModel):
    # Raw scanner input: an IMEI, a barcode or a SKU. The client does not
    # have to guess which (§6, FR-7.1).
    code: str


class ScanCustomerReturnLineCommand(
    ScanCustomerReturnLineCommandPayload, Command[ResultWithData[CustomerReturnData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    customer_return_id: UUID


class ScanCustomerReturnLineHandler(
    IRequestHandler[ResultWithData[CustomerReturnData], ScanCustomerReturnLineCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        scanner: CustomerReturnScanner,
        uow: TenantUnitOfWork,
    ) -> None:
        self._returns = returns
        self._invoices = invoices
        self._scanner = scanner
        self._uow = uow

    async def handle(
        self, request: ScanCustomerReturnLineCommand
    ) -> ResultWithData[CustomerReturnData]:
        spec = CustomerReturnForWrite(request.customer_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"customer return {request.customer_return_id} does not exist in "
                "this store",
                key="not_found",
                subject_key="customer_return",
            )
        document.assert_editable()

        invoice = await self._invoice_of(document)
        others = await self._returns.find(
            CustomerReturnsForInvoice(document.sales_invoice_id)
        )
        invoice_line, product, unit = await self._scanner.resolve(
            request.code, document=document, invoice=invoice, others=others
        )
        charged = self._charged_on(invoice_line, invoice)

        if unit is not None:
            if document.line_for_unit(unit.id) is not None:
                # A double-fire of the same trigger pull (§6).
                return self._result(document)
            document.lines.append(
                CustomerReturnLine(
                    id=uuid4(),
                    customer_return_id=document.id,
                    sales_invoice_line_id=invoice_line.id,
                    product_id=product.id,
                    device_unit_id=unit.id,
                    imei=unit.imei.value,
                    quantity=1,
                    currency=product.currency,
                    tracking_type=product.tracking_type,
                    charged_price=charged,
                    sold_quantity=invoice_line.quantity,
                    refund_price=charged,
                )
            )
            return await self._save(document, spec)

        remaining = self._scanner.remaining_for(
            invoice_line, document=document, others=others
        )
        if remaining <= 0:
            raise AlreadyReturnedError(
                f"all {invoice_line.quantity} of {product.sku} sold on "
                f"{invoice.number} have already come back",
                sku=product.sku,
                number=invoice.number,
            )

        existing = document.line_for_invoice_line(invoice_line.id)
        if existing is not None:
            existing.quantity += 1
            return await self._save(document, spec)

        document.lines.append(
            CustomerReturnLine(
                id=uuid4(),
                customer_return_id=document.id,
                sales_invoice_line_id=invoice_line.id,
                product_id=product.id,
                quantity=1,
                currency=product.currency,
                tracking_type=product.tracking_type,
                charged_price=charged,
                sold_quantity=invoice_line.quantity,
                refund_price=charged,
            )
        )
        return await self._save(document, spec)

    @staticmethod
    def _charged_on(line: SalesInvoiceLine, invoice: SalesInvoice) -> Money:
        """The refund's starting point and its ceiling (FR-4.9c).

        Nullable on the type because a *draft* line holds no price
        (FR-4.5b1), and unreachable here because a return only ever names a
        confirmed sale — confirming is what writes the snapshot.
        """
        if line.charged_price is None:
            raise NotFoundError(
                f"{invoice.number} has a line with no charged price to refund",
                key="not_found",
                subject_key="sales_invoice_line",
            )
        return line.charged_price

    async def _invoice_of(self, document: CustomerReturn) -> SalesInvoice:
        invoice = await self._invoices.find_one(
            SalesInvoiceById(document.sales_invoice_id)
        )
        if invoice is None:
            raise NotFoundError(
                f"sales invoice {document.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="sales_invoice",
            )
        return invoice

    async def _save(
        self, document: CustomerReturn, spec: CustomerReturnForWrite
    ) -> ResultWithData[CustomerReturnData]:
        await self._returns.update(document, spec)
        await self._uow.commit()
        return self._result(document)

    @staticmethod
    def _result(document: CustomerReturn) -> ResultWithData[CustomerReturnData]:
        return ResultWithData[CustomerReturnData].succeed_with_data(
            CustomerReturnData.from_entity(document)
        )
