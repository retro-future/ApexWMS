"""Resolving one beep onto an open Customer Return (PRD §6, FR-4.9a, FR-4.9b).

A removal scan asks whether the store *holds* what was scanned. A customer
return asks something narrower: did **this sale** sell it, and is any of it
still un-returned. Both answers live on the invoice, which is why this is
its own scanner rather than a fourth parameter on ``RemovalScanner``.

The refusals happen on the scan that caused them, while the customer is
still standing there (§6): a handset from a different invoice, or one this
store already took back, is rejected on the beep rather than when a
five-line return is submitted.

``CustomerReturnPoster`` re-asks whether the handset is still ``SOLD`` at
confirm, and that is not redundant: a draft reserves nothing, and two
returns can be open against the same sale at once.
"""

from collections.abc import Sequence

from application.common.repository import TenantDbRepository
from application.errors import NotFoundError
from application.services.device_unit_loader import DeviceUnitLoader
from application.specs import ProductByBarcode, ProductBySku
from domain.entities import (
    CustomerReturn,
    DeviceUnit,
    Product,
    SalesInvoice,
    SalesInvoiceLine,
)
from domain.enums import DocumentStatus, TrackingType
from domain.errors import AlreadyReturnedError, InvalidIMEIError, UnitNotReturnableError
from domain.value_objects import IMEI
from infrastructure.persistence.tenant.models import ProductModel


class CustomerReturnScanner:
    def __init__(
        self,
        units: DeviceUnitLoader,
        products: TenantDbRepository[Product, ProductModel],
    ) -> None:
        self._units = units
        self._products = products

    async def resolve(
        self,
        code: str,
        *,
        document: CustomerReturn,
        invoice: SalesInvoice,
        others: Sequence[CustomerReturn],
    ) -> tuple[SalesInvoiceLine, Product, DeviceUnit | None]:
        """What this scanned string names on the sale, if it may come back.

        Returns the invoice line being unwound, the catalog row, and — for a
        serialized scan — the handset. ``None`` for an accessory, which has
        no per-unit identity (§4.1).

        *others* is every return raised against this sale, this one
        included: it is filtered out here so no caller has to remember to.
        """
        found = await self._as_device(code)
        if found is not None:
            unit, product = found
            line = self._invoice_line_for_unit(unit, invoice)
            self._assert_unit_not_returned(unit, document, others)
            return line, product, unit

        product = await self._as_product(code)
        if product.tracking_type is TrackingType.SERIAL:
            raise UnitNotReturnableError(
                f"{product.sku} is a serialized model, and {document.number} takes "
                "back one named handset — scan the phone's IMEI rather than the "
                "model's barcode",
                key="scan_wants_imei",
            )
        line = self._invoice_line_for_product(product, invoice)
        return line, product, None

    def remaining_for(
        self,
        line: SalesInvoiceLine,
        *,
        document: CustomerReturn,
        others: Sequence[CustomerReturn],
    ) -> int:
        """How many of an accessory line are still un-returned (FR-4.9b).

        Counts this draft too, so a scan that would take the eleventh of ten
        is refused on the beep rather than at confirm.
        """
        claimants = (*self._except(document, others), document)
        taken = sum(
            other_line.quantity
            for other in claimants
            for other_line in other.lines
            if other_line.sales_invoice_line_id == line.id
            and self._counts_against_the_sale(other)
        )
        return line.quantity - taken

    @staticmethod
    def _except(
        document: CustomerReturn, others: Sequence[CustomerReturn]
    ) -> tuple[CustomerReturn, ...]:
        return tuple(other for other in others if other.id != document.id)

    @staticmethod
    def _counts_against_the_sale(document: CustomerReturn) -> bool:
        """Whether this return's lines still hold goods back from the sale.

        A cancelled return gave everything back and its goods are returnable
        again; a draft has not taken them yet but is about to, and letting a
        second draft claim the same handset would leave whichever confirmed
        second failing at the poster with the customer already paid.
        """
        return document.status is not DocumentStatus.CANCELLED

    def _assert_unit_not_returned(
        self,
        unit: DeviceUnit,
        document: CustomerReturn,
        others: Sequence[CustomerReturn],
    ) -> None:
        for other in self._except(document, others):
            if not self._counts_against_the_sale(other):
                continue
            if other.line_for_unit(unit.id) is not None:
                raise AlreadyReturnedError(
                    f"IMEI {unit.imei} is already on {other.number}",
                    imei=str(unit.imei),
                    number=other.number,
                )

    @staticmethod
    def _invoice_line_for_unit(unit: DeviceUnit, invoice: SalesInvoice) -> SalesInvoiceLine:
        line = invoice.line_for_unit(unit.id)
        if line is None:
            raise UnitNotReturnableError(
                f"IMEI {unit.imei} was not sold on {invoice.number}, so it cannot be "
                "returned against it",
                key="unit_not_on_invoice",
                imei=str(unit.imei),
                number=invoice.number,
            )
        return line

    @staticmethod
    def _invoice_line_for_product(
        product: Product, invoice: SalesInvoice
    ) -> SalesInvoiceLine:
        line = invoice.line_for_product(product.id)
        if line is None:
            raise UnitNotReturnableError(
                f"{product.sku} was not sold on {invoice.number}, so it cannot be "
                "returned against it",
                key="product_not_on_invoice",
                sku=product.sku,
                number=invoice.number,
            )
        return line

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
            raise NotFoundError(
                f"nothing in this store is identified by {code!r}",
                key="not_found_by_code",
                code=code,
            )
        return product
