"""Adding or growing an accessory line on a draft invoice (FR-4.2, FR-4.2c).

An accessory line is (product, quantity, catalog price) with no per-unit
identity, so the till scan and the manual catalog picker both resolve the
price the same way and merge into one line per product. The on-hand check
runs here so the seller is refused on the beep, not at confirm; the confirm
check (``InvoicePoster``) stays as the last word, because stock can drop
while the draft sits open.
"""

from uuid import uuid4

from application.common.repository import TenantDbRepository
from application.specs import StockLevelForPair
from domain.entities import Product, SalesInvoice, SalesInvoiceLine, StockLevel
from domain.enums import TrackingType
from domain.errors import InsufficientStockError, UnitNotSellableError
from domain.services import PriceResolver
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import StockLevelModel


class AccessoryLineWriter:
    def __init__(
        self, levels: TenantDbRepository[StockLevel, StockLevelModel]
    ) -> None:
        self._levels = levels

    async def add(
        self, invoice: SalesInvoice, product: Product, quantity: int = 1
    ) -> tuple[SalesInvoiceLine, Money]:
        if product.tracking_type is TrackingType.SERIAL:
            raise UnitNotSellableError(
                f"{product.sku} is a serialized model, and a sale is of one named "
                "handset — scan the phone's IMEI rather than the model's barcode",
                key="scan_wants_imei",
            )
        # Raises PriceNotSetError naming who can fix it: a QUANTITY product
        # with no catalog price has nowhere else a price could come from.
        resolved = PriceResolver.resolve(None, product)

        existing = invoice.line_for_product(product.id)
        wanted = quantity + (existing.quantity if existing is not None else 0)
        await self._assert_in_stock(invoice, product, wanted)

        if existing is not None:
            existing.quantity += quantity
            return existing, resolved

        line = SalesInvoiceLine(
            id=uuid4(),
            sales_invoice_id=invoice.id,
            product_id=product.id,
            quantity=quantity,
            currency=product.currency,
            tracking_type=product.tracking_type,
        )
        invoice.lines.append(line)
        return line, resolved

    async def _assert_in_stock(
        self, invoice: SalesInvoice, product: Product, wanted: int
    ) -> None:
        level = await self._levels.find_one(
            StockLevelForPair(product.id, invoice.location_id)
        )
        on_hand = 0 if level is None else level.quantity
        if on_hand < wanted:
            raise InsufficientStockError(
                f"this store holds {on_hand} of {product.sku} at {invoice.number}'s "
                f"location, and the invoice would sell {wanted} — there is no partial "
                "fulfilment (FR-4.7)",
                on_hand=on_hand,
                sku=product.sku,
                wanted=wanted,
                number=invoice.number,
            )
