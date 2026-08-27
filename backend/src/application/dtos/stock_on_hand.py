"""What the store is holding, grouped — FR-9.1, PRD §5.9.

Two tracking types with genuinely different cost rules feed one report
(§4.6): a serialized phone carries its own ``acquisition_cost``, while an
accessory's is a weighted-average pool replayed from the ledger. They meet
as ``OnHandBucket``, one subtotal in one currency, and the group holds a
``CurrencyTotals`` rather than a number: there is no field a som figure
could be added to a dollar one in.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from domain.value_objects import CurrencyTotals, Money


class StockGroupBy(StrEnum):
    LOCATION = "location"
    PRODUCT = "product"
    BRAND = "brand"


@dataclass(frozen=True, slots=True)
class OnHandBucket:
    """One group's subtotal in one currency, from one tracking type."""

    key: UUID | str | None
    label: str
    quantity: int
    value: Money


@dataclass(frozen=True, slots=True)
class AccessoryOnHand:
    """One accessory sitting at one location, before it has been valued.

    The pair is what ``CostPoolReader`` needs; the value cannot come out of
    the same statement because it is a replay, not a column.
    """

    product_id: UUID
    location_id: UUID
    quantity: int
    key: UUID | str | None
    label: str


@dataclass(frozen=True, slots=True)
class StockOnHandGroup:
    group_by: StockGroupBy
    key: UUID | str | None
    label: str
    quantity: int
    cost_value: CurrencyTotals
