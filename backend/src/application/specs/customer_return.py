"""The reads the customer return use cases need, one class each.

Written against ``CustomerReturnModel``, not ``CustomerReturn`` — ADR 0007.

Every spec eager-loads ``lines`` and, per line, the ``product`` (currency
and tracking type), the nullable ``device_unit`` (the scanned IMEI) and the
``sales_invoice_line`` — that last one because the refund ceiling is the
sale's own ``charged_price`` snapshot and is never copied onto the return.
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import CustomerReturnReason, DocumentStatus
from infrastructure.persistence.tenant.models import (
    CustomerReturnLineModel,
    CustomerReturnModel,
)

# Public because the invoice list batches returns over a whole page with
# its own inline spec, and it must load the same relationships the mapper
# reads (see ``list_sales_invoices``).
RETURN_WITH_LINES = (
    selectinload(CustomerReturnModel.lines).selectinload(CustomerReturnLineModel.product),
    selectinload(CustomerReturnModel.lines).selectinload(
        CustomerReturnLineModel.device_unit
    ),
    selectinload(CustomerReturnModel.lines).selectinload(
        CustomerReturnLineModel.sales_invoice_line
    ),
)


class CustomerReturnById(Specification[CustomerReturnModel]):
    """Read-only: no lock. For the reads that only display a return."""

    def __init__(self, customer_return_id: UUID) -> None:
        super().__init__(CustomerReturnModel)
        self.customer_return_id = customer_return_id
        self.where(CustomerReturnModel.id == customer_return_id)
        self.include(*RETURN_WITH_LINES)


class CustomerReturnForWrite(Specification[CustomerReturnModel]):
    """The specification a command uses to load a return it will mutate.

    Scanning a line, unscanning one, reducing a refund, confirming and
    cancelling all load through this: it locks ``customer_returns`` and
    brings the whole line collection so the mapper can sync it.
    """

    def __init__(self, customer_return_id: UUID) -> None:
        super().__init__(CustomerReturnModel)
        self.customer_return_id = customer_return_id
        self.where(CustomerReturnModel.id == customer_return_id)
        self.include(*RETURN_WITH_LINES)
        self.lock()


class CustomerReturnsForInvoice(Specification[CustomerReturnModel]):
    """Every return raised against one sale, in any status.

    What the double-return guard counts, and what stops a sale being
    cancelled out from under a return that already restocked its goods.
    """

    def __init__(self, sales_invoice_id: UUID) -> None:
        super().__init__(CustomerReturnModel)
        self.sales_invoice_id = sales_invoice_id
        self.where(CustomerReturnModel.sales_invoice_id == sales_invoice_id)
        self.include(*RETURN_WITH_LINES)


class CustomerReturnBrowse(Specification[CustomerReturnModel]):
    """The return list: number substring match, optional status, customer,
    location and reason filters, newest first with ``id`` as the tie-break."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        customer_id: UUID | None = None,
        location_id: UUID | None = None,
        reason: CustomerReturnReason | None = None,
    ) -> None:
        super().__init__(CustomerReturnModel)
        self.search = search
        self.status = status
        self.customer_id = customer_id
        self.location_id = location_id
        self.reason = reason
        if search:
            self.where(CustomerReturnModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            self.where(CustomerReturnModel.status == status.value)
        if customer_id is not None:
            self.where(CustomerReturnModel.customer_id == customer_id)
        if location_id is not None:
            self.where(CustomerReturnModel.location_id == location_id)
        if reason is not None:
            self.where(CustomerReturnModel.reason == reason.value)
        self.include(*RETURN_WITH_LINES)
        self.order(CustomerReturnModel.created_at.desc(), CustomerReturnModel.id)
