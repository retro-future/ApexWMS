"""Edit a product, and deactivate it (FR-2.4).

**There is no ``tracking_type`` or ``currency`` field here, deliberately.**
FR-2.1 makes both immutable once any stock movement references the
product; no movements table exists until M3, so rather than stub a check
that always passes, the API simply offers no way to change them. That is
strictly stronger than FR-2.1 asks for, and M3 does not need to relax it.

Deactivation is an update, never a delete: FR-2.4 keeps all history, and
nothing in this system hard-deletes.

Partial semantics come from ``model_fields_set``: a nullable field is
cleared only when the caller *sent* ``null``, so omitting ``barcode``
leaves it alone while sending ``"barcode": null`` removes it.
"""

from uuid import UUID

from pydantic import Field

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateBarcodeError, NotFoundError
from application.ports import ProductRepository, TenantUnitOfWork
from application.queries.get_product import ProductData
from application.services import SalePriceParser
from domain.entities import Product
from domain.value_objects import Barcode


class UpdateProductCommand(Command[ResultWithData[ProductData]]):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    barcode: str | None = None
    default_sale_price: str | int | None = None
    is_active: bool | None = None
    # A URL path segment, merged in by the router — see routers/products.py.
    product_id: UUID | None = Field(default=None, exclude=True)


class UpdateProductHandler(
    IRequestHandler[ResultWithData[ProductData], UpdateProductCommand]
):
    def __init__(
        self,
        products: ProductRepository,
        uow: TenantUnitOfWork,
        sale_price: SalePriceParser,
    ) -> None:
        self._products = products
        self._uow = uow
        self._sale_price = sale_price

    async def handle(self, request: UpdateProductCommand) -> ResultWithData[ProductData]:
        assert request.product_id is not None
        product = await self._products.get(request.product_id)
        if product is None:
            raise NotFoundError("no such product in this store")

        sent = request.model_fields_set
        if request.name is not None:
            product.name = request.name.strip()
        if request.is_active is not None:
            product.is_active = request.is_active
        if "brand" in sent:
            product.brand = request.brand
        if "model" in sent:
            product.model = request.model
        if "barcode" in sent:
            product.barcode = await self._resolved_barcode(request.barcode, product)
        if "default_sale_price" in sent:
            product.default_sale_price = self._sale_price.parse(
                request.default_sale_price, product.currency
            )

        # Re-run the entity's own invariants over the mutated state: a
        # barcode moved onto a SERIAL product, or a price that no longer
        # matches the currency, must fail here rather than reach the row.
        product.__post_init__()

        await self._products.update(product)
        await self._uow.commit()
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_product(product))

    async def _resolved_barcode(self, raw: str | None, product: Product) -> Barcode | None:
        if raw is None:
            return None
        barcode = Barcode.parse(raw)
        owner = await self._products.get_by_barcode(str(barcode))
        if owner is not None and owner.id != product.id:
            raise DuplicateBarcodeError(f"a product with barcode {barcode} already exists")
        return barcode
