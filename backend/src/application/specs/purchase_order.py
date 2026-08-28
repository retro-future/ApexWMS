"""The reads the purchase order use cases need, one class each.

Written against ``PurchaseOrderModel``, not ``PurchaseOrder`` — ADR 0007.

Every spec eager-loads ``lines`` and each line's ``product``: the line
carries the product's currency and tracking type (§4.5 rule 3), and both
relationships are ``lazy="raise"``.
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import DocumentStatus
from infrastructure.persistence.tenant.models import (
    PurchaseOrderLineModel,
    PurchaseOrderModel,
)

_WITH_LINES = selectinload(PurchaseOrderModel.lines).selectinload(
    PurchaseOrderLineModel.product
)


class PurchaseOrderById(Specification[PurchaseOrderModel]):
    """Read-only: no lock. For the reads that only display an order."""

    def __init__(self, purchase_order_id: UUID) -> None:
        super().__init__(PurchaseOrderModel)
        self.purchase_order_id = purchase_order_id
        self.where(PurchaseOrderModel.id == purchase_order_id)
        self.include(_WITH_LINES)


class PurchaseOrderForWrite(Specification[PurchaseOrderModel]):
    """The specification a command uses to load an order it will mutate.

    Locks ``purchase_orders``; the ``selectinload`` child queries stay
    unlocked, which is the same reach the old ``update_line`` had.
    """

    def __init__(self, purchase_order_id: UUID) -> None:
        super().__init__(PurchaseOrderModel)
        self.purchase_order_id = purchase_order_id
        self.where(PurchaseOrderModel.id == purchase_order_id)
        self.include(_WITH_LINES)
        self.lock()


class PurchaseOrderBrowse(Specification[PurchaseOrderModel]):
    """The order list: number substring match, optional status and
    supplier filters, newest first with ``id`` as the tie-break so a page
    boundary is stable."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        supplier_id: UUID | None = None,
    ) -> None:
        super().__init__(PurchaseOrderModel)
        self.search = search
        self.status = status
        self.supplier_id = supplier_id
        if search:
            self.where(PurchaseOrderModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            self.where(PurchaseOrderModel.status == status.value)
        if supplier_id is not None:
            self.where(PurchaseOrderModel.supplier_id == supplier_id)
        self.include(_WITH_LINES)
        self.order(PurchaseOrderModel.created_at.desc(), PurchaseOrderModel.id)
