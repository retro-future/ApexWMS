"""FR-2.1 / FR-2.6: a Manager creates a product with a tracking type and a
currency.

*currency* is optional on the wire and falls back to
``Product.default_currency_for`` — USD for a phone, UZS for an accessory.
The default lives in domain so no call site has to remember which is
which; the caller may still override it here, and only here (FR-2.6).

SKU and barcode uniqueness is checked before the insert so the caller
gets a 409 naming the field rather than an opaque integrity error. The
unique indexes are the backstop, not the check.

A product created *with* a price starts its price log at that price
(FR-2.19), the same way a unit priced at intake starts its own log there
(FR-3.11). The alternative — seeding ``default_sale_price`` directly and
logging only later changes — would leave the first price the one figure in
the catalog with no author and no timestamp.
"""

from uuid import uuid4

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateBarcodeError, DuplicateSkuError
from application.models import ProductData
from application.ports import Clock, TenantUnitOfWork
from application.services import CatalogCodeGenerator, ProductRepricer, SalePriceParser
from application.specs import ProductByBarcode, ProductBySku
from domain.entities import Product
from domain.enums import TrackingType
from domain.errors import BarcodeNotAllowedError
from domain.value_objects import SKU, Barcode, Currency
from infrastructure.persistence.tenant.models import ProductModel


class CreateProductCommand(Command[ResultWithData[ProductData]]):
    # Blank or omitted: the store lets the system assign one (PH-000001 /
    # AC-000001). A value the caller sends is used as-is.
    sku: str | None = None
    name: str
    tracking_type: TrackingType
    brand: str | None = None
    model: str | None = None
    currency: Currency | None = None
    barcode: str | None = None
    # QUANTITY only: generate an in-store EAN-13 when no barcode was sent.
    # An explicit barcode wins, so sending both is harmless.
    generate_barcode: bool = False
    # A string or a whole number, never a JSON float — see application/services/sale_price.py.
    default_sale_price: str | int | None = None
    price_reason: str | None = None


class CreateProductHandler(
    IRequestHandler[ResultWithData[ProductData], CreateProductCommand]
):
    def __init__(
        self,
        products: TenantDbRepository[Product, ProductModel],
        clock: Clock,
        uow: TenantUnitOfWork,
        sale_price: SalePriceParser,
        repricer: ProductRepricer,
        codes: CatalogCodeGenerator,
    ) -> None:
        self._products = products
        self._clock = clock
        self._uow = uow
        self._sale_price = sale_price
        self._repricer = repricer
        self._codes = codes

    async def handle(self, request: CreateProductCommand) -> ResultWithData[ProductData]:
        if request.sku and request.sku.strip():
            sku = SKU.parse(request.sku)
            if await self._products.exists(ProductBySku(str(sku))):
                raise DuplicateSkuError(f"a product with SKU {sku} already exists", sku=str(sku))
        else:
            sku = await self._codes.next_sku(request.tracking_type)

        barcode = await self._resolve_barcode(request)

        currency = request.currency or Product.default_currency_for(request.tracking_type)
        product = Product(
            id=uuid4(),
            sku=sku,
            name=request.name.strip(),
            brand=request.brand,
            model=request.model,
            tracking_type=request.tracking_type,
            currency=currency,
            barcode=barcode,
            # Deliberately unpriced here: the price arrives below, through
            # the log, so that even the first one has an author and a
            # timestamp. The row is inserted first because the log's
            # foreign key points at it.
            default_sale_price=None,
            is_active=True,
            created_at=self._clock.now(),
        )
        await self._products.add(product)

        price = self._sale_price.parse(request.default_sale_price, currency)
        if price is not None:
            await self._repricer.set_price(product, price, request.price_reason)
            await self._products.update(product)

        await self._uow.commit()
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_entity(product))

    async def _resolve_barcode(self, request: CreateProductCommand) -> Barcode | None:
        if request.barcode:
            barcode = Barcode.parse(request.barcode)
            if await self._products.exists(ProductByBarcode(str(barcode))):
                raise DuplicateBarcodeError(
                    f"a product with barcode {barcode} already exists", barcode=str(barcode)
                )
            return barcode
        if not request.generate_barcode:
            return None
        if request.tracking_type is TrackingType.SERIAL:
            raise BarcodeNotAllowedError(
                "a SERIAL product is identified by IMEI, not by barcode (FR-2.3)",
                key="barcode_on_serial",
            )
        return await self._codes.next_barcode()
