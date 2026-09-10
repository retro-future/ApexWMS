"""One scanned handset on an open Goods Receipt — PRD §5.3, FR-1.7.

The split here is the same one ``DeviceUnitData`` makes, and for the same
reason (§2.1, FR-7.2):

- **Everyone** sees the IMEI, the condition and the **asking price**,
  including a Storekeeper. ``needsAskingPrice`` is what turns "the confirm
  was refused" into a worklist they can act on — they cannot price the
  handset themselves, but they can see which ones are holding the receipt
  up and go and get someone who can.
- **Only ``Permission.Cost.View``** sees the acquisition cost and the som
  handed over. Hiding the cost is what makes a margin uncomputable, which
  is the actual requirement; hiding the sale price would only break the
  counter.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import GoodsReceiptLine, ReceivedUnit
from domain.enums import DeviceCondition
from domain.value_objects import Currency, Money


class ReceivedUnitData(CamelModel):
    id: UUID
    imei: str
    imei2: str | None
    serial_number: str | None
    condition: DeviceCondition
    currency: Currency
    asking_price: MoneyData | None
    # True while this handset is not NEW and carries no asking price —
    # exactly what FR-3.10 will refuse the confirm over.
    needs_asking_price: bool
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: MoneyData | None = None
    # "paid 4 200 000 so'm" — a string, never a number, so no caller can
    # add it to anything (§4.5b, FR-3.4d).
    cash_paid: str | None = None

    @classmethod
    def from_entity(
        cls, unit: ReceivedUnit, line: GoodsReceiptLine, *, show_cost: bool
    ) -> ReceivedUnitData:
        data = cls(
            id=unit.id,
            imei=str(unit.imei),
            imei2=str(unit.imei2) if unit.imei2 else None,
            serial_number=unit.serial_number,
            condition=unit.condition,
            currency=line.currency,
            asking_price=MoneyData.from_entity(unit.asking_price),
            needs_asking_price=unit.needs_asking_price,
        )
        if not show_cost:
            return data

        cash_paid = None
        if unit.cash_paid_minor is not None and unit.cash_paid_currency is not None:
            cash_paid = Money(unit.cash_paid_minor, unit.cash_paid_currency).format()
        return data.model_copy(
            update={
                "acquisition_cost": MoneyData.from_entity(unit.acquisition_cost),
                "cash_paid": cash_paid,
            }
        )
