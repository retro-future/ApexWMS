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
``default_sale_price`` is the one exception — see ``ProductRepricer``: a
price that has been set cannot be sent back to ``null``, because the log
it projects from has no row shape meaning "no longer priced".
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import DuplicateBarcodeError, NotFoundError
from application.models import ProductData
from application.ports import TenantUnitOfWork
from application.services import ProductRepricer, SalePriceParser
from application.specs import ProductBarcodeTakenByAnother, ProductForWrite
from domain.entities import Product
from domain.value_objects import Barcode
from infrastructure.persistence.tenant.models import ProductModel


class UpdateProductCommandPayload(CamelModel):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    barcode: str | None = None
    default_sale_price: str | int | None = None
    # Free text, never mandatory: FR-2.19 records *that* a price moved and
    # who moved it. Making the store justify each change was not asked for.
    price_reason: str | None = None
    is_active: bool | None = None


class UpdateProductCommand(UpdateProductCommandPayload, Command[ResultWithData[ProductData]]):
    # A URL path segment, filled in by the router — never sent by the client.
    product_id: UUID


class UpdateProductHandler(
    IRequestHandler[ResultWithData[ProductData], UpdateProductCommand]
):
    def __init__(
        self,
        products: TenantDbRepository[Product, ProductModel],
        uow: TenantUnitOfWork,
        sale_price: SalePriceParser,
        repricer: ProductRepricer,
    ) -> None:
        self._products = products
        self._uow = uow
        self._sale_price = sale_price
        self._repricer = repricer

    async def handle(self, request: UpdateProductCommand) -> ResultWithData[ProductData]:
        product = await self._products.find_one(ProductForWrite(request.product_id))
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
            # Through the repricer, never by assignment: the price is the
            # projection of its log (FR-2.19), so the two move as one.
            await self._repricer.set_price(
                product,
                self._sale_price.parse(request.default_sale_price, product.currency),
                request.price_reason,
            )

        # Re-run the entity's own invariants over the mutated state: a
        # barcode moved onto a SERIAL product, or a price that no longer
        # matches the currency, must fail here rather than reach the row.
        product.__post_init__()

        await self._products.update(product)
        await self._uow.commit()
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_entity(product))

    async def _resolved_barcode(self, raw: str | None, product: Product) -> Barcode | None:
        if raw is None:
            return None
        barcode = Barcode.parse(raw)
        if await self._products.exists(ProductBarcodeTakenByAnother(str(barcode), product.id)):
            raise DuplicateBarcodeError(f"a product with barcode {barcode} already exists")
        return barcode
