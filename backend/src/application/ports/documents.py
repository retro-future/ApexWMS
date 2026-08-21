"""Rendering a document to a file the store can hand over (PRD §5.8).

A port rather than a direct call so ``application`` never learns what a PDF
library is: the handler asks for bytes, and whether those came from fpdf2,
a template engine or a print service is ``infrastructure``'s business.
"""

from typing import Protocol
from uuid import UUID

from application.dtos import Letterhead
from domain.entities import SalesInvoice


class InvoiceRenderer(Protocol):
    """FR-8.1: a confirmed sale, on paper, with the store's own details."""

    def render(
        self, invoice: SalesInvoice, letterhead: Letterhead, descriptions: dict[UUID, str]
    ) -> bytes:
        """*descriptions* maps a line id to the text to print for it.

        Passed in rather than looked up here: a renderer that could reach a
        repository would be doing a handler's job, and what a line reads as
        (a model name, an IMEI beneath it) is a choice the caller has
        already made.
        """
        ...
