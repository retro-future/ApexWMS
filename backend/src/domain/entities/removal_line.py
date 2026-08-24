"""A line that takes goods off the shelf and books no revenue (PRD §5.5, §5.6).

A Supplier Return and a Write-Off differ entirely in *why* stock leaves and
what the money ledger calls it, and not at all in what a line looks like:
a product, either one named handset or a count of an accessory, and the
currency and tracking type its product decides. So the shape is stated once
here and each document adds only its own parent id — the same split
``Document`` makes for the headers.

A Sales Invoice line looks similar and is deliberately not this: it carries
three prices, an approver and a note, because a sale is a negotiation.
Nothing leaves under a return or a write-off at a price.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import TrackingType
from domain.errors import InvalidLineError
from domain.value_objects import Currency


@dataclass(eq=False, kw_only=True)
class RemovalLine(UuidEntity, TenantEntity):
    product_id: UUID
    # Set for a SERIAL line and None for a QUANTITY one: an accessory has no
    # per-unit identity to point at (§4.1).
    device_unit_id: UUID | None = None
    quantity: int = 1
    # Both the product's, carried onto the line by the repository's join.
    currency: Currency
    tracking_type: TrackingType
    # The handset's, carried by the same join. Read-only: the line is keyed
    # by device unit, and unscanning names the IMEI because that is what the
    # operator is holding.
    imei: str | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidLineError(f"a line for {self.quantity} units moves nothing")
        if self.is_serial:
            if self.device_unit_id is None:
                raise InvalidLineError("a serialized line must name the handset it moves")
            if self.quantity != 1:
                raise InvalidLineError(
                    "a serialized line moves one named handset, so its quantity is 1"
                )
        elif self.device_unit_id is not None:
            raise InvalidLineError("a quantity line names no device unit (§4.1)")

    @property
    def is_serial(self) -> bool:
        return self.tracking_type is TrackingType.SERIAL
