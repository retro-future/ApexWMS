"""An intention to buy (PRD §4.4, FR-3.1).

A PO is a piece of paper sent to a supplier; goods arrive later, on a Goods
Receipt, and that is what writes the ledgers. Confirming a PO writes
nothing to either ledger — it only fixes the order's numbers, so the
supplier and the store are looking at the same figures.

A line's price is optional at every stage. The store may raise an order
before a supplier has quoted, confirm it to lock the quantities, and only
learn the cost when the goods arrive — pricing then happens on the Goods
Receipt, which has its own price gate at confirm (FR-3.4b, FR-3.10).
``unit_cost`` may be filled in while the order is a draft, through
``price_purchase_order_line``, but confirm never requires it.

Each line takes its currency from its product (FR-2.7), so one order may
hold a USD phone line and a UZS accessory line at once. There is no
document-level currency and no combined total anywhere — ``subtotals``
returns one figure per currency present, side by side.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import TrackingType
from domain.errors import (
    CurrencyMismatchError,
    InvalidLineError,
    InvalidMoneyError,
)
from domain.services import SubtotalsCalculator
from domain.value_objects import Currency, Money


@dataclass(eq=False, kw_only=True)
class PurchaseOrderLine(UuidEntity, TenantEntity):
    purchase_order_id: UUID
    product_id: UUID
    quantity: int
    unit_cost: Money | None = None
    # The product's, carried onto the line by the repository's join so the
    # rules above need no catalog lookup of their own. Kept even while
    # ``unit_cost`` is still null, since the line has to say what it will
    # eventually be denominated in.
    currency: Currency
    tracking_type: TrackingType

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidLineError(f"a line for {self.quantity} units orders nothing")
        if self.unit_cost is not None:
            if self.unit_cost.is_negative:
                raise InvalidMoneyError("a unit cost may not be negative")
            if self.unit_cost.currency is not self.currency:
                raise CurrencyMismatchError(
                    f"line cost is {self.unit_cost.currency.value} but the product is "
                    f"priced in {self.currency.value} (§4.5 rule 3)"
                )

    @property
    def total_cost(self) -> Money | None:
        if self.unit_cost is None:
            return None
        return self.unit_cost * self.quantity


@dataclass(eq=False, kw_only=True)
class PurchaseOrder(Document):
    supplier_id: UUID
    lines: list[PurchaseOrderLine] = field(default_factory=list)

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-3.2: lock the order's quantities. Prices stay optional."""
        self.assert_editable()
        super().confirm(now, user_id)

    def subtotals(self) -> dict[Currency, Money]:
        return SubtotalsCalculator.by_currency(line.total_cost for line in self.lines)

    def ordered_quantities(self) -> dict[UUID, int]:
        """How much of each product was ordered — FR-3.9's denominator."""
        ordered: dict[UUID, int] = {}
        for line in self.lines:
            ordered[line.product_id] = ordered.get(line.product_id, 0) + line.quantity
        return ordered
