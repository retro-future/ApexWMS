"""The payload both price logs return — §4.5b.

``ProductPriceChange`` and ``DeviceUnitPriceChange`` differ only in what
they are keyed on, and the question they answer is identical: *what did
this cost, when did it change, and who changed it?* So there is one
payload, and a client that can render a model's history renders a
handset's without learning a second shape.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import DeviceUnitPriceChange, ProductPriceChange


class PriceChangeData(CamelModel):
    id: UUID
    occurred_at: datetime
    # Null on the first row: that is where pricing started, not a gap.
    old_price: MoneyData | None
    new_price: MoneyData
    reason: str | None
    user_id: UUID

    @classmethod
    def from_entity(
        cls, change: ProductPriceChange | DeviceUnitPriceChange
    ) -> PriceChangeData:
        return cls(
            id=change.id,
            occurred_at=change.occurred_at,
            old_price=MoneyData.from_entity(change.old_price),
            new_price=MoneyData.from_entity(change.new_price),
            reason=change.reason,
            user_id=change.user_id,
        )
