"""What one beep of the scanner at the till returns — PRD §6, FR-4.2.

Its own file rather than a branch of ``SalesInvoiceData`` because the scan
route returns it on its own: §6 gives the whole round trip 200ms, and
re-serialising a fifty-line invoice per beep is the thing that budget
rules out.

``resolvedPrice`` here is **display only and is not persisted**. It is what
the line would charge if the invoice were confirmed at this instant, shown
so the counter can read a figure to the customer. The invoice writes no
price until confirm, where resolution runs again (FR-4.5b1) — so a markdown
made between this beep and the confirm reaches the customer, and this
number is a quote, never a reservation.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from application.models.sales_invoice import SalesInvoiceLineData
from domain.entities import SalesInvoice, SalesInvoiceLine
from domain.value_objects import Money


class InvoiceScanResultData(CamelModel):
    line: SalesInvoiceLineData
    # How many lines the invoice holds now — the running count §6 wants
    # after every beep, so the operator never has to look away to check.
    line_count: int
    resolved_price: MoneyData
    product_id: UUID
    device_unit_id: UUID | None

    @classmethod
    def from_entity(
        cls, invoice: SalesInvoice, line: SalesInvoiceLine, resolved: Money
    ) -> InvoiceScanResultData:
        return cls(
            line=SalesInvoiceLineData.from_entity(line),
            line_count=len(invoice.lines),
            resolved_price=MoneyData.from_entity(resolved),
            product_id=line.product_id,
            device_unit_id=line.device_unit_id,
        )
