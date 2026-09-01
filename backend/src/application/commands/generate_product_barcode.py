"""Give an existing accessory an in-store EAN-13 (FR-2.3).

Separate from ``update_product`` because it takes no input the client
chooses — the number comes from the per-tenant counter — and because it
refuses on a product that already has one rather than overwriting it.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import BarcodeAlreadySetError, NotFoundError
from application.models import ProductData
from application.ports import TenantUnitOfWork
from application.services import CatalogCodeGenerator
from application.specs import ProductForWrite
from domain.entities import Product
from domain.enums import TrackingType
from domain.errors import BarcodeNotAllowedError
from infrastructure.persistence.tenant.models import ProductModel


class GenerateProductBarcodeCommand(Command[ResultWithData[ProductData]]):
    # URL path segment, filled in by the router — never sent by the client.
    product_id: UUID


class GenerateProductBarcodeHandler(
    IRequestHandler[ResultWithData[ProductData], GenerateProductBarcodeCommand]
):
    def __init__(
        self,
        products: TenantDbRepository[Product, ProductModel],
        uow: TenantUnitOfWork,
        codes: CatalogCodeGenerator,
    ) -> None:
        self._products = products
        self._uow = uow
        self._codes = codes

    async def handle(
        self, request: GenerateProductBarcodeCommand
    ) -> ResultWithData[ProductData]:
        product = await self._products.find_one(ProductForWrite(request.product_id))
        if product is None:
            raise NotFoundError("no such product in this store")
        if product.tracking_type is TrackingType.SERIAL:
            raise BarcodeNotAllowedError(
                "a SERIAL product is identified by IMEI, not by barcode (FR-2.3)"
            )
        if product.barcode is not None:
            raise BarcodeAlreadySetError(
                f"product {product.sku} already carries barcode {product.barcode}"
            )

        product.barcode = await self._codes.next_barcode()
        await self._products.update(product)
        await self._uow.commit()
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_entity(product))
