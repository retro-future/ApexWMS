"""The lifecycle all six documents share (PRD §4.4).

```
DRAFT ──confirm──▶ CONFIRMED ──cancel──▶ CANCELLED
```

A draft is a shopping list and touches nothing. Confirming ends that, and
from there every field is immutable — a confirmed document that is wrong
is cancelled and re-entered, never patched, because it has already written
rows into two append-only ledgers.

Only the transitions live here. **What makes a particular document
confirmable is its own business**: a Goods Receipt counts its scans and
checks its prices, a Purchase Order has nothing to check at all. Subclasses
override ``confirm`` to state their invariants and then delegate here for
the state change, so the one lifecycle stays in one place while the rules
stay with the document that owns them.

Each subclass's ``subtotals`` goes through ``domain.services.SubtotalsCalculator``
(not here) — putting it behind entity construction would import
``domain.services``, which itself depends on ``domain.entities`` (see
``PriceResolver``), and Python cannot resolve that cycle at module load time.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import DocumentStatus
from domain.errors import DocumentNotConfirmedError, DocumentNotDraftError


@dataclass(eq=False, kw_only=True)
class Document(UuidEntity, TenantEntity):
    # Human-readable and per-tenant sequential: PO-2026-0001, GR-2026-0042.
    number: str
    status: DocumentStatus
    note: str | None = None
    created_by: UUID
    created_at: datetime
    confirmed_by: UUID | None = None
    confirmed_at: datetime | None = None
    cancelled_by: UUID | None = None
    cancelled_at: datetime | None = None
    # Its own field rather than an overwrite of ``note``: the reason a
    # document was called off and whatever it said when it was raised are
    # two different facts, and losing the second to record the first is how
    # the audit trail thins out.
    cancellation_reason: str | None = None

    def assert_editable(self) -> None:
        """FR-3.12: lines and amounts change only while the document is a draft."""
        if not self.status.is_editable:
            raise DocumentNotDraftError(
                f"{self.number} is {self.status.value} and can no longer be edited — "
                "correct it by cancelling and re-entering (§4.4)",
                number=self.number,
            )

    def confirm(self, now: datetime, user_id: UUID) -> None:
        self.assert_editable()
        self.status = DocumentStatus.CONFIRMED
        self.confirmed_at = now
        self.confirmed_by = user_id

    def cancel(self, now: datetime, user_id: UUID, reason: str | None = None) -> None:
        """Move to CANCELLED so the caller may write the compensating rows.

        Refusing a second cancellation is this method's real job. Reversing
        an already-reversed document would re-apply it, and
        ``LedgerPoster.reverse`` deliberately holds no such guard — the
        document's own state is the one place that knows.
        """
        if self.status is not DocumentStatus.CONFIRMED:
            raise DocumentNotConfirmedError(
                f"{self.number} is {self.status.value}; only a confirmed document "
                "is cancelled, and only once",
                key="cancel_needs_confirmed",
                number=self.number,
            )
        self.status = DocumentStatus.CANCELLED
        self.cancelled_at = now
        self.cancelled_by = user_id
        self.cancellation_reason = reason
