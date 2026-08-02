"""One entry in a handset's price history (PRD §4.5b, FR-2.15).

Used stock that does not move gets cut, then cut again — that is the core
discipline of the trade, and *"we paid $300, asked $420, cut it twice,
sold at $360"* is a question the owner asks of a specific handset months
later. So repricing is a row, not an assignment, and
``DeviceUnit.asking_price`` is the latest one.

Same shape and same discipline as ``ProductPriceChange``: the amounts are
bare minor units in the product's currency, which the repository recovers
on read. This introduces a table, not a concept.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.errors import CurrencyMismatchError, InvalidMoneyError
from domain.value_objects import Money


@dataclass(eq=False, kw_only=True)
class DeviceUnitPriceChange(UuidEntity, TenantEntity):
    device_unit_id: UUID
    occurred_at: datetime
    # None only for the first pricing — at intake, or the first time anyone
    # priced a unit a stock count turned up (FR-6.4b).
    old_price: Money | None = None
    new_price: Money
    reason: str | None = None
    user_id: UUID

    def __post_init__(self) -> None:
        if self.new_price.is_negative:
            raise InvalidMoneyError("an asking price may not be negative")
        if self.old_price is not None and self.old_price.currency is not self.new_price.currency:
            raise CurrencyMismatchError(
                f"repriced from {self.old_price.currency.value} to "
                f"{self.new_price.currency.value}, but a unit is denominated by its "
                "product and a product's currency is immutable (§4.5 rule 3)"
            )
