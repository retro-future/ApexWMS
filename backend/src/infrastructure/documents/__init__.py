"""Rendering documents to files (PRD §5.8).

Implements ``application/ports/documents.py``. Nothing in ``application``
imports from here — the port lives there, the PDF library lives here.
"""

from infrastructure.documents.invoice_pdf import PdfInvoiceRenderer

__all__ = ["PdfInvoiceRenderer"]
