"""The Sales Invoice reads that carry lines or a stack of filters.

Written against ``SalesInvoiceModel`` — ADR 0007. Every spec eager-loads
``lines`` and each line's ``product``: the line carries the product's
currency and tracking type (§4.5 rule 3), and both relationships are
``lazy="raise"``.
"""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import DocumentStatus
from infrastructure.persistence.tenant.models import (
    CustomerModel,
    DeviceUnitModel,
    SalesInvoiceLineModel,
    SalesInvoiceModel,
)

_WITH_LINES = selectinload(SalesInvoiceModel.lines).selectinload(
    SalesInvoiceLineModel.product
)


class SalesInvoiceById(Specification[SalesInvoiceModel]):
    """Read-only: no lock. For the reads that only display an invoice."""

    def __init__(self, sales_invoice_id: UUID) -> None:
        super().__init__(SalesInvoiceModel)
        self.sales_invoice_id = sales_invoice_id
        self.where(SalesInvoiceModel.id == sales_invoice_id)
        self.include(_WITH_LINES)


class SalesInvoiceForWrite(Specification[SalesInvoiceModel]):
    """The spec a command uses to load an invoice it will mutate.

    Locks ``sales_invoices``; the ``selectinload`` child queries stay
    unlocked, the same reach the old ``update_line`` had.
    """

    def __init__(self, sales_invoice_id: UUID) -> None:
        super().__init__(SalesInvoiceModel)
        self.sales_invoice_id = sales_invoice_id
        self.where(SalesInvoiceModel.id == sales_invoice_id)
        self.include(_WITH_LINES)
        self.lock()


class SalesInvoiceBrowse(Specification[SalesInvoiceModel]):
    """The sales list. One search box, three ways a seller looks a sale up:
    the invoice number, the customer's name or phone, or a handset's IMEI.
    The customer and IMEI matches are correlated ``EXISTS`` rather than
    joins so a two-line invoice cannot come back twice and a walk-in sale
    is not dropped. Newest first, ``id`` breaking ties for a stable page."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        customer_id: UUID | None = None,
        location_id: UUID | None = None,
    ) -> None:
        super().__init__(SalesInvoiceModel)
        self.search = search
        self.status = status
        self.customer_id = customer_id
        self.location_id = location_id
        if search:
            term = f"%{search.strip()}%"
            customer_match = (
                select(CustomerModel.id)
                .where(
                    CustomerModel.id == SalesInvoiceModel.customer_id,
                    or_(
                        CustomerModel.full_name.ilike(term),
                        CustomerModel.phone.ilike(term),
                    ),
                )
                .exists()
            )
            imei_match = (
                select(SalesInvoiceLineModel.id)
                .join(
                    DeviceUnitModel,
                    DeviceUnitModel.id == SalesInvoiceLineModel.device_unit_id,
                )
                .where(
                    SalesInvoiceLineModel.sales_invoice_id == SalesInvoiceModel.id,
                    DeviceUnitModel.imei.ilike(term),
                )
                .exists()
            )
            self.where(
                or_(
                    SalesInvoiceModel.number.ilike(term), customer_match, imei_match
                )
            )
        if status is not None:
            self.where(SalesInvoiceModel.status == status.value)
        if customer_id is not None:
            self.where(SalesInvoiceModel.customer_id == customer_id)
        if location_id is not None:
            self.where(SalesInvoiceModel.location_id == location_id)
        self.include(_WITH_LINES)
        self.order(SalesInvoiceModel.created_at.desc(), SalesInvoiceModel.id)
