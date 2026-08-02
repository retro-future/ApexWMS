"""Why stock moved (PRD §4.3).

There is deliberately **no ``REVERSAL`` member.** Cancelling a confirmed
document does not delete its movements — it writes compensating ones "in
the opposite direction" (§4.3 rule 2) — and those compensations keep the
type of the thing being undone, flipping only the sign of
``quantity_delta``.

The alternative is worse than it looks. A separate reversal type would
have to be remembered, and excluded, by every report that groups by
movement type: a sales figure that forgot it would count a cancelled sale
as a sale. Carrying the reversal as a sign means summing the deltas is
always the right answer, and the compensation is still plainly visible as
its own row.
"""

from enum import StrEnum


class MovementType(StrEnum):
    RECEIPT = "receipt"
    SALE = "sale"
    SUPPLIER_RETURN = "supplier_return"
    COUNT_ADJUSTMENT = "count_adjustment"
    WRITE_OFF = "write_off"
