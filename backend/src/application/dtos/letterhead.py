"""What a printed document puts at the top of the page (FR-8.1)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Letterhead:
    """The store's own details, as they appear on a PDF.

    Both are optional because provisioning cannot know either one: a store
    sets them once, in settings. A document with neither still prints, with
    its number and its lines — the letterhead is decoration on a record
    whose contents are the point.
    """

    business_name: str | None = None
    address: str | None = None
