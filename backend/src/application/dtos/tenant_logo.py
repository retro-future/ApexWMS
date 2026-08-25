"""The store's mark, as bytes on their way to a page (FR-8.1)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantLogo:
    """An image and what kind of image it is.

    The content type is stored rather than re-sniffed on every read: it was
    checked once, against the bytes themselves, when the Owner uploaded it.
    """

    content: bytes
    content_type: str
