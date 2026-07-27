from uuid import UUID

from sqlalchemy import or_, select

from domain.catalog import TrackingType
from domain.entities import Product
from domain.value_objects import SKU, Barcode, Currency, Money
from infrastructure.persistence.tenant.models import ProductModel

from .base import TenantCrudRepository


class SqlProductRepository(TenantCrudRepository[Product, UUID, ProductModel]):
    model = ProductModel


    def _to_entity(self, row: ProductModel) -> Product:
        currency = Currency(row.currency)
        return Product(
            id=row.id,
            sku=SKU(row.sku),
            name=row.name,
            brand=row.brand,
            model=row.model,
            tracking_type=TrackingType(row.tracking_type),
            currency=currency,
            barcode=Barcode(row.barcode) if row.barcode else None,
            # The stored integer is only meaningful with its currency: USD
            # and UZS do not share an exponent (PRD §4.5).
            default_sale_price=(
                Money(row.default_sale_price_minor, currency)
                if row.default_sale_price_minor is not None
                else None
            ),
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def _to_model(self, entity: Product) -> ProductModel:
        price = entity.default_sale_price
        return ProductModel(
            id=entity.id,
            sku=str(entity.sku),
            name=entity.name,
            brand=entity.brand,
            model=entity.model,
            tracking_type=entity.tracking_type.value,
            currency=entity.currency.value,
            barcode=str(entity.barcode) if entity.barcode else None,
            default_sale_price_minor=price.amount_minor if price else None,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )

    def _apply(self, row: ProductModel, entity: Product) -> None:
        # sku, tracking_type and currency are absent on purpose: FR-2.1
        # makes the last two immutable, and the SKU is the catalog's stable
        # identifier. There is no update path for any of them.
        row.name = entity.name
        row.brand = entity.brand
        row.model = entity.model
        row.barcode = str(entity.barcode) if entity.barcode else None
        row.default_sale_price_minor = (
            entity.default_sale_price.amount_minor if entity.default_sale_price else None
        )
        row.is_active = entity.is_active

    async def get_by_sku(self, sku: str) -> Product | None:
        return await self._find_one(ProductModel.sku == sku)

    async def get_by_barcode(self, barcode: str) -> Product | None:
        return await self._find_one(ProductModel.barcode == barcode)

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
        tracking_type: TrackingType | None = None,
    ) -> tuple[list[Product], int]:
        stmt = select(ProductModel)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ProductModel.sku.ilike(term),
                    ProductModel.name.ilike(term),
                    ProductModel.brand.ilike(term),
                    ProductModel.barcode.ilike(term),
                )
            )
        if is_active is not None:
            stmt = stmt.where(ProductModel.is_active.is_(is_active))
        if tracking_type is not None:
            stmt = stmt.where(ProductModel.tracking_type == tracking_type.value)
        return await self._page(stmt.order_by(ProductModel.created_at), page, page_size)
