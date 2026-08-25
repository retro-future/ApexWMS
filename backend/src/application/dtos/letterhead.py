"""What a printed document puts at the top of the page (FR-8.1)."""

from dataclasses import dataclass

from application.dtos.tenant_logo import TenantLogo


@dataclass(frozen=True, slots=True)
class Letterhead:
    """The store's own details, as they appear on a PDF.

    All three are optional because provisioning cannot know any of them: a
    store sets them once, in settings. A document with none still prints,
    with its number and its lines — the letterhead is decoration on a record
    whose contents are the point.

    The logo arrives by its own route and has its own setter, so a settings
    write carrying only text cannot drop the image.
    """

    business_name: str | None = None
    address: str | None = None
    logo: TenantLogo | None = None
