"""Payment log reads (§4.7). Written against ``PaymentModel`` (ADR 0007).

Only the per-invoice read is a class — every sales-invoice command and
query lists an invoice's payments. It stores ``sales_invoice_id`` as a
plain attribute for the in-memory fake. Everything else (a page of
invoices, the whole log, one payment's reversal) is inline in its handler.
"""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import PaymentModel


class PaymentsForInvoice(Specification[PaymentModel]):
    """One invoice's payments, oldest first — the down payment the confirm
    recorded and any compensating reversals."""

    def __init__(self, sales_invoice_id: UUID) -> None:
        super().__init__(PaymentModel)
        self.sales_invoice_id = sales_invoice_id
        self.where(PaymentModel.sales_invoice_id == sales_invoice_id)
        self.order(PaymentModel.occurred_at, PaymentModel.id)
