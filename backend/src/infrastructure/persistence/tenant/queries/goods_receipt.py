"""GoodsReceipt reads that are not "load a whole receipt".

Three joined reads that fold rows into a `dict`, a scalar or a DTO, which a
`Specification` cannot express (ADR 0007). Split off `SqlGoodsReceiptRepository`
when the aggregate moved to the generic repository. Same shape as the other
query services in this package.
"""

from uuid import UUID

from sqlalchemy import Row, select

from application.dtos import UnitOrigin
from domain.enums import AcquisitionSource, DocumentStatus
from infrastructure.persistence.tenant.models import (
    CustomerModel,
    GoodsReceiptLineModel,
    GoodsReceiptModel,
    SupplierModel,
)
from infrastructure.types import TenantSession


class SqlGoodsReceiptQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def received_quantities(self, purchase_order_id: UUID) -> dict[UUID, int]:
        """FR-3.9's numerator: confirmed receipts only.

        A draft has received nothing, so counting it would report an order
        as complete while the goods are still on the van.
        """
        stmt = (
            select(GoodsReceiptLineModel.product_id, GoodsReceiptLineModel.quantity)
            .join(
                GoodsReceiptModel,
                GoodsReceiptModel.id == GoodsReceiptLineModel.goods_receipt_id,
            )
            .where(
                GoodsReceiptModel.purchase_order_id == purchase_order_id,
                GoodsReceiptModel.status == DocumentStatus.CONFIRMED.value,
            )
        )
        received: dict[UUID, int] = {}
        for product_id, quantity in await self._session.execute(stmt):
            received[product_id] = received.get(product_id, 0) + quantity
        return received

    async def supplier_of(self, receipt_id: UUID) -> UUID | None:
        stmt = select(GoodsReceiptModel.supplier_id).where(
            GoodsReceiptModel.id == receipt_id
        )
        return await self._session.scalar(stmt)

    async def origin_of(self, receipt_id: UUID) -> UnitOrigin | None:
        """FR-9.2's first line: a supplier, or the walk-in it was traded in
        from (FR-3.3b). Both sides are outer-joined because exactly one of
        them is ever set."""
        stmt = (
            select(
                GoodsReceiptModel.acquisition_source,
                GoodsReceiptModel.supplier_id,
                SupplierModel.name,
                GoodsReceiptModel.customer_id,
                CustomerModel.full_name,
            )
            .outerjoin(SupplierModel, SupplierModel.id == GoodsReceiptModel.supplier_id)
            .outerjoin(CustomerModel, CustomerModel.id == GoodsReceiptModel.customer_id)
            .where(GoodsReceiptModel.id == receipt_id)
        )
        row = (await self._session.execute(stmt)).first()
        return None if row is None else self._to_origin(row)

    @staticmethod
    def _to_origin(
        row: Row[tuple[str, UUID | None, str, UUID | None, str]],
    ) -> UnitOrigin:
        source, supplier_id, supplier, customer_id, customer = row._tuple()
        supplier_name: str | None = supplier
        customer_name: str | None = customer
        return UnitOrigin(
            acquisition_source=AcquisitionSource(source),
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            customer_id=customer_id,
            customer_name=customer_name,
        )
