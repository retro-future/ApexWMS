"""FR-4.2, FR-4.2b, FR-4.3, FR-4.4: one beep of the scanner at the till.

One endpoint, two possible answers, exactly as §6's contract says: the
client sends a string and the server decides whether it named a handset or
a catalog row. The operator's scanner does not know what it just read.

**An IMEI** adds the phone it names. It is refused on the scan that caused
it — while the operator is still holding the thing — if it is not
``IN_STOCK`` (FR-4.3), if it is held somewhere other than this invoice's
location (FR-4.4), or if no price resolves for it (FR-4.2b). That last one
is the milestone's signature refusal: a used handset with no price of its
own is **not** quoted the model's new price, and the message names an Owner
or Manager because the Seller reading it cannot fix it themselves (§2.1).

**A barcode** adds or increments an accessory line. A repeat barcode
increments rather than doing nothing, because three identical cases across
the counter are three sales — that is the one place this deliberately
departs from §6's "an identical scan is a no-op", which is right for a
serial line and wrong here. A repeat *IMEI* is still a no-op: one phone,
one line, and a double-fired trigger must not be punished.

A barcode that resolves to a SERIAL product is refused rather than
guessed at: a model has many handsets and the sale is of one of them, so
the operator is told to scan the IMEI.

Nothing here writes a price. The line records what a Manager overrode, if
anything, and the resolved figure is returned for the counter to read
aloud — a quote, not a reservation. Resolution runs again at confirm
(FR-4.5b1).
"""

from uuid import UUID, uuid4

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import InvoiceScanResultData
from application.ports import TenantUnitOfWork
from application.services import AccessoryLineWriter, DeviceUnitLoader
from application.specs import ProductByBarcode, ProductBySku, SalesInvoiceForWrite
from domain.entities import DeviceUnit, Product, SalesInvoice, SalesInvoiceLine
from domain.enums import DeviceStatus
from domain.errors import InvalidIMEIError, UnitNotSellableError, WrongLocationError
from domain.services import PriceResolver
from domain.value_objects import IMEI, Money
from infrastructure.persistence.tenant.models import ProductModel, SalesInvoiceModel


class ScanInvoiceLineCommandPayload(CamelModel):
    # Raw scanner input: an IMEI, a barcode or a SKU. The client does not
    # have to guess which (§6, FR-7.1).
    code: str


class ScanInvoiceLineCommand(
    ScanInvoiceLineCommandPayload, Command[ResultWithData[InvoiceScanResultData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    sales_invoice_id: UUID


class ScanInvoiceLineHandler(
    IRequestHandler[ResultWithData[InvoiceScanResultData], ScanInvoiceLineCommand]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        units: DeviceUnitLoader,
        products: TenantDbRepository[Product, ProductModel],
        accessory: AccessoryLineWriter,
        uow: TenantUnitOfWork,
    ) -> None:
        self._invoices = invoices
        self._units = units
        self._products = products
        self._accessory = accessory
        self._uow = uow

    async def handle(
        self, request: ScanInvoiceLineCommand
    ) -> ResultWithData[InvoiceScanResultData]:
        spec = SalesInvoiceForWrite(request.sales_invoice_id)
        invoice = await self._invoices.find_one(spec)
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store"
            )
        invoice.assert_editable()

        found = await self._as_device(request.code)
        if found is not None:
            unit, product = found
            line, resolved, changed = self._sell_unit(invoice, unit, product)
        else:
            product = await self._as_product(request.code)
            line, resolved = await self._accessory.add(invoice, product)
            changed = True

        if changed:
            await self._invoices.update(invoice, spec)
            await self._uow.commit()
        return self._result(invoice, line, resolved)

    def _sell_unit(
        self, invoice: SalesInvoice, unit: DeviceUnit, product: Product
    ) -> tuple[SalesInvoiceLine, Money, bool]:
        already = invoice.line_for_unit(unit.id)
        if already is not None:
            # A double-fire of the same trigger pull. One phone, one line
            # — nothing changes and the same answer comes back (§6).
            return already, PriceResolver.resolve(unit, product), False

        self._assert_sellable(invoice, unit)
        # Raises PriceNotSetError naming who can fix it (FR-4.2b). Refused
        # here rather than added as a zero-priced or catalog-priced line.
        resolved = PriceResolver.resolve(unit, product)

        line = SalesInvoiceLine(
            id=uuid4(),
            sales_invoice_id=invoice.id,
            product_id=product.id,
            device_unit_id=unit.id,
            quantity=1,
            currency=product.currency,
            tracking_type=product.tracking_type,
        )
        invoice.lines.append(line)
        return line, resolved, True

    async def _as_device(self, code: str) -> tuple[DeviceUnit, Product] | None:
        """A scanned string is an IMEI only if it parses as one.

        ``InvalidIMEIError`` is swallowed rather than raised: a 13-digit
        barcode is not a malformed IMEI, it is a barcode, and the caller
        never said which it was sending (§6).
        """
        try:
            imei = IMEI.parse(code)
        except InvalidIMEIError:
            return None
        return await self._units.load_by_imei(str(imei))

    async def _as_product(self, code: str) -> Product:
        product = await self._products.find_one(ProductByBarcode(code))
        if product is None:
            product = await self._products.find_one(ProductBySku(code))
        if product is None:
            raise NotFoundError(f"nothing in this store is identified by {code!r}")
        return product

    @staticmethod
    def _assert_sellable(invoice: SalesInvoice, unit: DeviceUnit) -> None:
        if unit.status is not DeviceStatus.IN_STOCK:
            raise UnitNotSellableError(
                f"IMEI {unit.imei} is {unit.status.value} and cannot be sold (FR-4.3)",
                imei=str(unit.imei),
                status=unit.status.value,
            )
        if unit.location_id != invoice.location_id:
            raise WrongLocationError(
                f"IMEI {unit.imei} is held at another location, and {invoice.number} "
                "sells from its own (FR-4.4)",
                imei=str(unit.imei),
                number=invoice.number,
            )

    @staticmethod
    def _result(
        invoice: SalesInvoice, line: SalesInvoiceLine, resolved: Money
    ) -> ResultWithData[InvoiceScanResultData]:
        return ResultWithData[InvoiceScanResultData].succeed_with_data(
            InvoiceScanResultData.from_entity(invoice, line, resolved)
        )
