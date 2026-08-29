"""TenantDB ports that are neither an aggregate repository nor a query
service: the singleton settings row, and the document-number counter.

No method takes a ``tenant_id`` — the session these are bound to *is* the
tenant, so there is no filter to forget.
"""

from typing import Protocol

from application.dtos import Letterhead, TenantLogo
from domain.enums import DocumentType


class TenantSettingsRepository(Protocol):
    """The singleton settings row seeded at provisioning — not aggregate CRUD."""

    async def get_timezone(self) -> str: ...

    async def set_timezone(self, timezone: str) -> None: ...

    async def get_letterhead(self) -> Letterhead:
        """The store's own details, for the top of a printed document (FR-8.1)."""
        ...

    async def set_letterhead(self, letterhead: Letterhead) -> None:
        """Writes the text only. The logo has its own setter, so a settings
        write that carries no image cannot silently drop one."""
        ...

    async def set_logo(self, logo: TenantLogo | None) -> None:
        """``None`` clears it."""
        ...


class DocumentNumberAllocator(Protocol):
    """The per-tenant sequence behind ``PO-2026-0001`` (§4.4).

    One counter per (document type, year), handed out under a row lock so
    two operators filling in receipts at the same counter cannot be given
    the same number. ``DocumentNumberer`` turns the int into the string.
    """

    async def next_number(self, document_type: DocumentType, year: int) -> int: ...
