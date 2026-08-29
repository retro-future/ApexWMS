"""The reads the catalog use cases need, one class each.

Written against ``ProductModel``, not ``Product`` (ADR 0007). ``ProductBySku``
and ``ProductByBarcode`` serve double duty: the scanner reads the whole
product back through them, and create/update run them through ``exists()``
as uniqueness probes. The browse spec carries its filters as plain
attributes so the in-memory fake can read them without an ORM.
"""

from uuid import UUID

from sqlalchemy import or_

from application.common.specification import Specification
from domain.enums import TrackingType
from infrastructure.persistence.tenant.models import ProductModel


class ProductForWrite(Specification[ProductModel]):
    """Locks the row for a command that loads a product to mutate it."""

    def __init__(self, product_id: UUID) -> None:
        super().__init__(ProductModel)
        self.product_id = product_id
        self.where(ProductModel.id == product_id)
        self.lock()


class ProductBySku(Specification[ProductModel]):
    """SKU is unique within the store (FR-2.1). What the scanner reads, and
    a uniqueness probe for create."""

    def __init__(self, sku: str) -> None:
        super().__init__(ProductModel)
        self.sku = sku
        self.where(ProductModel.sku == sku)


class ProductByBarcode(Specification[ProductModel]):
    """Barcode is unique among products that have one (FR-2.1). What the
    scanner reads, and a uniqueness probe for create."""

    def __init__(self, barcode: str) -> None:
        super().__init__(ProductModel)
        self.barcode = barcode
        self.exclude_id: UUID | None = None
        self.where(ProductModel.barcode == barcode)


class ProductBarcodeTakenByAnother(Specification[ProductModel]):
    """``ProductByBarcode`` for an edit: the product being edited does not
    collide with itself."""

    def __init__(self, barcode: str, product_id: UUID) -> None:
        super().__init__(ProductModel)
        self.barcode = barcode
        self.exclude_id: UUID | None = product_id
        self.where(ProductModel.barcode == barcode, ProductModel.id != product_id)


class ProductBrowse(Specification[ProductModel]):
    """One page of the catalog: case-insensitive match over SKU, name,
    brand and barcode, optional active and tracking-type filters, oldest
    first."""

    def __init__(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        tracking_type: TrackingType | None = None,
    ) -> None:
        super().__init__(ProductModel)
        self.search = search
        self.is_active = is_active
        self.tracking_type = tracking_type
        if search:
            term = f"%{search.strip()}%"
            self.where(
                or_(
                    ProductModel.sku.ilike(term),
                    ProductModel.name.ilike(term),
                    ProductModel.brand.ilike(term),
                    ProductModel.barcode.ilike(term),
                )
            )
        if is_active is not None:
            self.where(ProductModel.is_active.is_(is_active))
        if tracking_type is not None:
            self.where(ProductModel.tracking_type == tracking_type.value)
        self.order(ProductModel.created_at, ProductModel.id)
