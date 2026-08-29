"""The reads the goods receipt use cases need, one class each.

Written against ``GoodsReceiptModel``, not ``GoodsReceipt`` (ADR 0007).

Every spec eager-loads ``lines``, and per line the scanned ``units`` and the
``product`` (currency and tracking type). The three projection reads that are
not "load a whole receipt" (received quantities, supplier of, origin of) live
in ``SqlGoodsReceiptQueries``, not here.
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import AcquisitionSource, DocumentStatus
from infrastructure.persistence.tenant.models import (
    GoodsReceiptLineModel,
    GoodsReceiptModel,
)

_WITH_GRAPH = (
    selectinload(GoodsReceiptModel.lines).selectinload(GoodsReceiptLineModel.units),
    selectinload(GoodsReceiptModel.lines).selectinload(GoodsReceiptLineModel.product),
)


class GoodsReceiptById(Specification[GoodsReceiptModel]):
    """Read-only: no lock. For the reads that only display a receipt."""

    def __init__(self, goods_receipt_id: UUID) -> None:
        super().__init__(GoodsReceiptModel)
        self.goods_receipt_id = goods_receipt_id
        self.where(GoodsReceiptModel.id == goods_receipt_id)
        self.include(*_WITH_GRAPH)


class GoodsReceiptForWrite(Specification[GoodsReceiptModel]):
    """The specification a command uses to load a receipt it will mutate.

    Confirming, cancelling, scanning, unscanning and pricing all load through
    this: it locks ``goods_receipts`` and brings the whole line and unit
    graph so the mapper can sync it.
    """

    def __init__(self, goods_receipt_id: UUID) -> None:
        super().__init__(GoodsReceiptModel)
        self.goods_receipt_id = goods_receipt_id
        self.where(GoodsReceiptModel.id == goods_receipt_id)
        self.include(*_WITH_GRAPH)
        self.lock()


class GoodsReceiptBrowse(Specification[GoodsReceiptModel]):
    """The receipt list: number substring match, optional status and
    acquisition-source filters, newest first with ``id`` as the tie-break."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        acquisition_source: AcquisitionSource | None = None,
    ) -> None:
        super().__init__(GoodsReceiptModel)
        self.search = search
        self.status = status
        self.acquisition_source = acquisition_source
        if search:
            self.where(GoodsReceiptModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            self.where(GoodsReceiptModel.status == status.value)
        if acquisition_source is not None:
            self.where(
                GoodsReceiptModel.acquisition_source == acquisition_source.value
            )
        self.include(*_WITH_GRAPH)
        self.order(GoodsReceiptModel.created_at.desc(), GoodsReceiptModel.id)
