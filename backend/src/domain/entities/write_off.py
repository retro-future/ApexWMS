"""Stock destroyed, lost or stolen (PRD §4.4, §5.6, FR-6.5).

The one document that books a pure loss: goods leave, nothing comes back,
and ``WRITE_OFF_LOSS`` carries their book value out of inventory. Confirming
marks each handset ``WRITTEN_OFF`` and decrements accessory levels.

Near-identical to ``SupplierReturn`` in shape and entirely different in
meaning, which is why they are two documents rather than one with a flag.
A return is expected to produce a credit from the supplier; a write-off is
the store absorbing the cost, and the month-end report reads the two in
different columns (§5.10).

A count shortage lands a handset in the same ``WRITTEN_OFF`` status without
passing through here — it books ``COUNT_ADJUSTMENT`` under its own count
(§4.6), because "we looked and it was gone" and "we know what happened to
it" are different claims.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.entities.document import Document
from domain.entities.removal_line import RemovalLine
from domain.enums import WriteOffReason
from domain.errors import DuplicateScanError, EmptyDocumentError


@dataclass(eq=False, kw_only=True)
class WriteOffLine(RemovalLine):
    write_off_id: UUID


@dataclass(eq=False, kw_only=True)
class WriteOff(Document):
    location_id: UUID
    # Mandatory (FR-6.5), and an enum so the loss report can group by it.
    # Whatever detail it does not carry goes in ``note``.
    reason: WriteOffReason
    lines: list[WriteOffLine] = field(default_factory=list)

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-6.5: everything that must be true before the loss is booked."""
        self.assert_editable()
        self._assert_has_lines()
        self._assert_no_unit_twice()
        super().confirm(now, user_id)

    def line_for_unit(self, device_unit_id: UUID) -> WriteOffLine | None:
        """The line already writing this handset off — the idempotent re-scan (§6)."""
        return next(
            (line for line in self.lines if line.device_unit_id == device_unit_id),
            None,
        )

    def line_for_product(self, product_id: UUID) -> WriteOffLine | None:
        """The quantity line already holding *product_id*, if there is one."""
        return next(
            (
                line
                for line in self.lines
                if line.product_id == product_id and not line.is_serial
            ),
            None,
        )

    def _assert_has_lines(self) -> None:
        if not self.lines:
            raise EmptyDocumentError(
                f"{self.number} has no lines — nothing is being written off",
                number=self.number,
            )

    def _assert_no_unit_twice(self) -> None:
        seen: set[UUID] = set()
        for line in self.lines:
            if line.device_unit_id is None:
                continue
            if line.device_unit_id in seen:
                raise DuplicateScanError(
                    f"{self.number} writes the same handset off twice — "
                    "one phone, one line",
                    number=self.number,
                )
            seen.add(line.device_unit_id)
