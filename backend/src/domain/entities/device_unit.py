"""One physical handset — the heart of the system (PRD §4.2).

Two handsets of the same model are not the same thing, and this entity is
where that stops being a slogan. Each carries **its own** acquisition cost
(two identical iPhones bought a month apart cost different money, and
average costing would destroy that) and **its own** asking price (two used
handsets of the same model are not worth the same money, §4.5b). Cost and
price are the same problem seen from opposite sides, so they sit next to
each other and are set by the same person at the same moment.

Neither carries a currency of its own. A unit cannot be denominated
differently from the catalog row it belongs to (§4.5 rule 3), so both
inherit the product's currency and the repository recovers it on read —
which is also why ``__post_init__`` insists the two agree.

``status`` and ``location_id`` are **projections of ``stock_movements``**
(§4.3), not fields anyone assigns from outside a ledger posting.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import DeviceCondition, DeviceStatus, DocumentType
from domain.errors import (
    CurrencyMismatchError,
    InvalidDeviceUnitError,
    InvalidMoneyError,
    UnitNotRepriceableError,
)
from domain.value_objects import IMEI, Currency, Money


@dataclass(eq=False, kw_only=True)
class DeviceUnit(UuidEntity, TenantEntity):
    imei: IMEI
    # Dual-SIM handsets carry a second IMEI; non-phone serialized goods
    # carry a plain serial instead. Both are optional and neither is the
    # identity — ``imei`` is.
    imei2: IMEI | None = None
    serial_number: str | None = None
    product_id: UUID
    status: DeviceStatus
    location_id: UUID | None = None
    acquisition_cost: Money
    asking_price: Money | None = None
    condition: DeviceCondition
    # What physically changed hands, when that is not what was booked — a
    # trade-in bought for som against a USD catalog row (§4.5b). A bare
    # pair and **never** a ``Money``, precisely so it cannot be added to
    # anything: it enters no ledger, no inventory value, no margin, and no
    # report total. Any figure anywhere that contains it is a bug.
    cash_paid_minor: int | None = None
    cash_paid_currency: Currency | None = None
    # How the unit entered stock. Nullable because it need not have come
    # through a receipt at all: a stock count's *unexpected* list creates
    # units for handsets the system did not know it had (FR-6.4b).
    source_document_type: DocumentType | None = None
    source_document_id: UUID | None = None
    created_at: datetime

    def __post_init__(self) -> None:
        if self.acquisition_cost.is_negative:
            raise InvalidMoneyError("an acquisition cost may not be negative")
        if self.asking_price is not None:
            if self.asking_price.currency is not self.acquisition_cost.currency:
                raise CurrencyMismatchError(
                    f"asking price is {self.asking_price.currency.value} but the unit was "
                    f"bought in {self.acquisition_cost.currency.value}; a unit cannot be "
                    "denominated differently from its product (§4.5 rule 3)"
                )
            if self.asking_price.is_negative:
                raise InvalidMoneyError("an asking price may not be negative")

        if (self.cash_paid_minor is None) != (self.cash_paid_currency is None):
            raise InvalidMoneyError(
                "cash_paid needs both an amount and a currency, or neither"
            )

        if self.status.is_on_hand and self.location_id is None:
            raise InvalidDeviceUnitError(
                f"a unit that is {self.status.value} is somewhere — it needs a location"
            )
        if not self.status.is_on_hand and self.location_id is not None:
            raise InvalidDeviceUnitError(
                f"a unit that is {self.status.value} has left the store — it holds no location"
            )

    @property
    def currency(self) -> Currency:
        """The product's currency, as inherited by every amount here."""
        return self.acquisition_cost.currency

    def assert_repriceable(self) -> None:
        """FR-2.16: only stock still on the shelf may be repriced."""
        if not self.status.is_on_hand:
            raise UnitNotRepriceableError(
                f"IMEI {self.imei} is {self.status.value} and can no longer be repriced"
            )

    def cash_paid_display(self) -> str | None:
        """*"paid 4 200 000 so'm"*, for the unit's page and the IMEI trace.

        A string, not a ``Money``: the whole point of the pair is that this
        figure can be **read** and never **summed** (§4.5b, FR-3.4d).
        """
        if self.cash_paid_minor is None or self.cash_paid_currency is None:
            return None
        return Money(self.cash_paid_minor, self.cash_paid_currency).format()
