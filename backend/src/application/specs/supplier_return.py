"""The reads the supplier return use cases need, one class each.

Written against ``SupplierReturnModel``, not ``SupplierReturn`` — ADR 0007.

Every spec eager-loads ``lines`` and, per line, the ``product`` (currency
and tracking type) and the nullable ``device_unit`` (the scanned IMEI).
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import DocumentStatus, SupplierReturnReason
from infrastructure.persistence.tenant.models import (
    SupplierReturnLineModel,
    SupplierReturnModel,
)

_WITH_LINES = (
    selectinload(SupplierReturnModel.lines).selectinload(SupplierReturnLineModel.product),
    selectinload(SupplierReturnModel.lines).selectinload(
        SupplierReturnLineModel.device_unit
    ),
)


class SupplierReturnById(Specification[SupplierReturnModel]):
    """Read-only: no lock. For the reads that only display a return."""

    def __init__(self, supplier_return_id: UUID) -> None:
        super().__init__(SupplierReturnModel)
        self.supplier_return_id = supplier_return_id
        self.where(SupplierReturnModel.id == supplier_return_id)
        self.include(*_WITH_LINES)


class SupplierReturnForWrite(Specification[SupplierReturnModel]):
    """The specification a command uses to load a return it will mutate.

    Scanning a line, unscanning one, confirming and cancelling all load
    through this: it locks ``supplier_returns`` and brings the whole line
    collection so the mapper can sync it.
    """

    def __init__(self, supplier_return_id: UUID) -> None:
        super().__init__(SupplierReturnModel)
        self.supplier_return_id = supplier_return_id
        self.where(SupplierReturnModel.id == supplier_return_id)
        self.include(*_WITH_LINES)
        self.lock()


class SupplierReturnBrowse(Specification[SupplierReturnModel]):
    """The return list: number substring match, optional status, supplier
    and reason filters, newest first with ``id`` as the tie-break."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        supplier_id: UUID | None = None,
        reason: SupplierReturnReason | None = None,
    ) -> None:
        super().__init__(SupplierReturnModel)
        self.search = search
        self.status = status
        self.supplier_id = supplier_id
        self.reason = reason
        if search:
            self.where(SupplierReturnModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            self.where(SupplierReturnModel.status == status.value)
        if supplier_id is not None:
            self.where(SupplierReturnModel.supplier_id == supplier_id)
        if reason is not None:
            self.where(SupplierReturnModel.reason == reason.value)
        self.include(*_WITH_LINES)
        self.order(SupplierReturnModel.created_at.desc(), SupplierReturnModel.id)
