"""Goods going back to the supplier (PRD §4.4, §5.5).

The inverse of a Goods Receipt: the same supplier, the same location, the
opposite sign. Confirming marks each handset ``RETURNED_TO_SUPPLIER``,
decrements accessory levels, and books ``SUPPLIER_RETURN_CREDIT`` for what
the goods were carried at.

Every rule here is a pure function of the return's own lines, the same
split ``GoodsReceipt`` keeps. Whether a handset is *still* on the shelf
needs the live unit, so FR-5.2's check belongs to ``SupplierReturnPoster``
rather than here — a draft can sit open while the phone is sold from under
it.

A return always names a supplier, with no ``TRADE_IN`` counterpart: a
handset bought from a walk-in has nobody to go back to, and reselling or
scrapping it are a sale and a write-off respectively.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.entities.document import Document
from domain.entities.removal_line import RemovalLine
from domain.enums import SupplierReturnReason
from domain.errors import DuplicateScanError, EmptyDocumentError, ReceiptSourceError


@dataclass(eq=False, kw_only=True)
class SupplierReturnLine(RemovalLine):
    supplier_return_id: UUID


@dataclass(eq=False, kw_only=True)
class SupplierReturn(Document):
    supplier_id: UUID
    location_id: UUID
    reason: SupplierReturnReason
    lines: list[SupplierReturnLine] = field(default_factory=list)

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-5.3: everything that must be true before goods go back."""
        self.assert_editable()
        self._assert_has_supplier()
        self._assert_has_lines()
        self._assert_no_unit_twice()
        super().confirm(now, user_id)

    def line_for_unit(self, device_unit_id: UUID) -> SupplierReturnLine | None:
        """The line already returning this handset — the idempotent re-scan (§6)."""
        return next(
            (line for line in self.lines if line.device_unit_id == device_unit_id),
            None,
        )

    def line_for_product(self, product_id: UUID) -> SupplierReturnLine | None:
        """The quantity line already holding *product_id*, if there is one."""
        return next(
            (
                line
                for line in self.lines
                if line.product_id == product_id and not line.is_serial
            ),
            None,
        )

    def _assert_has_supplier(self) -> None:
        # Checked again at confirm rather than trusted from construction:
        # the column is non-null, and this is what says so in the one place
        # a reader looks for the confirm rules.
        if self.supplier_id is None:
            raise ReceiptSourceError(
                f"{self.number} sends goods back but names no supplier (FR-5.1)"
            )

    def _assert_has_lines(self) -> None:
        if not self.lines:
            raise EmptyDocumentError(
                f"{self.number} has no lines — nothing is going back"
            )

    def _assert_no_unit_twice(self) -> None:
        seen: set[UUID] = set()
        for line in self.lines:
            if line.device_unit_id is None:
                continue
            if line.device_unit_id in seen:
                raise DuplicateScanError(
                    f"{self.number} returns the same handset twice — one phone, one line"
                )
            seen.add(line.device_unit_id)
