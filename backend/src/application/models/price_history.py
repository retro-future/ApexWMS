"""The payload both price logs return — §4.5b.

``ProductPriceChange`` and ``DeviceUnitPriceChange`` differ only in what
they are keyed on, and the question they answer is identical: *what did
this cost, when did it change, and who changed it?* So there is one
payload, and a client that can render a model's history renders a
handset's without learning a second shape.

Prices are exact major-unit ``Decimal``s — pydantic serializes those as
JSON strings, so no float ever carries an amount (PRD §4.5).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from domain.entities import DeviceUnitPriceChange, ProductPriceChange
from domain.value_objects import Currency


class PriceChangeData(CamelModel):
    id: UUID
    occurred_at: datetime
    # Null on the first row: that is where pricing started, not a gap.
    old_price: Decimal | None
    new_price: Decimal
    old_price_minor: int | None
    new_price_minor: int
    currency: Currency
    reason: str | None
    user_id: UUID

    @classmethod
    def from_entity(
        cls, change: ProductPriceChange | DeviceUnitPriceChange
    ) -> PriceChangeData:
        old = change.old_price
        return cls(
            id=change.id,
            occurred_at=change.occurred_at,
            old_price=old.as_major() if old else None,
            new_price=change.new_price.as_major(),
            old_price_minor=old.amount_minor if old else None,
            new_price_minor=change.new_price.amount_minor,
            currency=change.new_price.currency,
            reason=change.reason,
            user_id=change.user_id,
        )
