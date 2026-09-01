"""Rendering a document to a file the store can hand over (PRD §5.8).

Ports rather than direct calls so ``application`` never learns what a PDF
library is: the handler asks for bytes, and whether those came from fpdf2,
a template engine or a print service is ``infrastructure``'s business.

One Protocol per document type rather than one generic renderer, because
what each page needs genuinely differs — an order names its supplier, a
return names its supplier and the shelf the goods left, and an invoice
needs neither.

Every ``render`` takes *descriptions*, mapping a line id to the text to
print for it. Passed in rather than looked up: a renderer that could reach
a repository would be doing a handler's job, and what a line reads as (a
model name, an IMEI beneath it) is a choice the caller has already made.
"""

from typing import Protocol
from uuid import UUID

from application.dtos import Letterhead, MonthEndReport, ProductLabel
from application.localization.locale import Locale
from domain.entities import PurchaseOrder, SalesInvoice, SupplierReturn
from domain.enums import LabelLayout


class InvoiceRenderer(Protocol):
    """FR-8.1: a confirmed sale, on paper, with the store's own details."""

    def render(
        self,
        invoice: SalesInvoice,
        letterhead: Letterhead,
        descriptions: dict[UUID, str],
        locale: Locale,
    ) -> bytes: ...


class PurchaseOrderRenderer(Protocol):
    """FR-3.2: the order as the supplier sees it."""

    def render(
        self,
        order: PurchaseOrder,
        letterhead: Letterhead,
        supplier: str | None,
        descriptions: dict[UUID, str],
        locale: Locale,
    ) -> bytes: ...


class SupplierReturnRenderer(Protocol):
    """FR-5.3: the note that travels with the goods."""

    def render(
        self,
        document: SupplierReturn,
        letterhead: Letterhead,
        supplier: str | None,
        location: str | None,
        descriptions: dict[UUID, str],
        locale: Locale,
    ) -> bytes: ...


class LabelRenderer(Protocol):
    """FR-2.3-adjacent: a product's shelf label, with a scannable code.

    Not a ``Document`` renderer — a label has no number, no confirm
    timestamp and no lines somebody named, so it takes neither a document
    nor *descriptions*.
    """

    def render(
        self,
        label: ProductLabel,
        letterhead: Letterhead,
        layout: LabelLayout,
        copies: int,
    ) -> bytes: ...


class MonthEndReportRenderer(Protocol):
    """FR-10.9: the period close on paper. The only renderer here whose
    subject is not a ``Document``, and so the only one that takes no
    *descriptions* — a report has no lines somebody named."""

    def render(self, report: MonthEndReport, letterhead: Letterhead) -> bytes: ...
