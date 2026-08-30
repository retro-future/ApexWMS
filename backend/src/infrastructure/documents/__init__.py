"""Rendering documents to files (PRD §5.8).

Implements ``application/ports/documents.py``. Nothing in ``application``
imports from here — the port lives there, the PDF library lives here.
"""

from infrastructure.documents.invoice_pdf import PdfInvoiceRenderer
from infrastructure.documents.month_end_pdf import PdfMonthEndReportRenderer
from infrastructure.documents.page import DocumentPage, DocumentPageFactory
from infrastructure.documents.purchase_order_pdf import PdfPurchaseOrderRenderer
from infrastructure.documents.supplier_return_pdf import PdfSupplierReturnRenderer

__all__ = [
    "DocumentPage",
    "DocumentPageFactory",
    "PdfInvoiceRenderer",
    "PdfMonthEndReportRenderer",
    "PdfPurchaseOrderRenderer",
    "PdfSupplierReturnRenderer",
]
