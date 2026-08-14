"""One requested document line, on its way from a command to the builder.

Not a wire shape: each command declares its own Pydantic line item, because
that item is part of that one message. This is what those items are turned
into so ``DocumentLineBuilder`` can serve both documents without importing
either command module.

``unit_cost`` is a string or a whole number, never a JSON float — the same
rule every amount in the system follows (§4.5 rule 2).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LineInput:
    product_id: UUID
    quantity: int
    # ``Decimal`` is here for the one caller that is not a wire value: a
    # receipt pre-filled from a Purchase Order passes that order's stored
    # ``Money`` back through as major units.
    unit_cost: str | int | Decimal | None = None
