"""One confirmed line charged something other than the resolved price (FR-9.7).

A read row, not an entity: it is stitched from the invoice, its line, the
product and the handset in a single query, because the report is a flat
table and re-loading four aggregates per row to flatten them again would
be work done twice.

``difference`` is signed, and deliberately so. A model sold *above* its
asking price is information too, so the report never takes an absolute
value.

The approver and the customer are carried by name as well as by id: the
pattern the report exists to surface is *"one manager, one customer, over
and over"*, and a page of UUIDs does not show it.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class PriceDeviation:
    invoice_id: UUID
    invoice_number: str
    confirmed_at: datetime
    customer_id: UUID | None
    customer_name: str | None
    product_id: UUID
    product_name: str
    # Null on an accessory line — there is no handset to name (§4.1).
    imei: str | None
    resolved_price: Money
    charged_price: Money
    price_approved_by: UUID | None
    price_approved_by_name: str | None
    price_note: str | None

    @property
    def difference(self) -> Money:
        return self.charged_price - self.resolved_price
