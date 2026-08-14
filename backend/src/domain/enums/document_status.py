"""Where a document is in the one lifecycle they all share (PRD §4.4).

``DRAFT`` is a shopping list: freely editable, and it touches nothing —
no movement, no financial transaction, no customer debt. ``CONFIRMED`` is
the moment that stops being true, and from there the document is immutable
in every field. A confirmed document that is wrong is ``CANCELLED``, which
writes compensating rows into both ledgers rather than deleting anything.

There is deliberately no way back. ``CANCELLED`` is terminal because a
document that could return to ``DRAFT`` would leave the compensations it
already wrote describing a document that no longer exists, and the whole
audit chain of §4.3 rests on that never happening.
"""

from enum import StrEnum


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

    @property
    def is_editable(self) -> bool:
        """Whether lines and amounts may still be changed (§4.4, FR-3.12)."""
        return self is DocumentStatus.DRAFT
