"""Unit repricing (FR-2.15, FR-2.16, FR-2.21): the log row and its
projection, together.

``DeviceUnit.asking_price`` is *the latest row of*
``device_unit_price_changes`` (§4.5b) — the same discipline
``ProductRepricer`` applies to the catalog price, deliberately shaped the
same way, because two price logs that drift apart in style drift apart in
behaviour soon after.

Repricing moves no money. It writes **no** ``FinancialTransaction``, and it
does not touch ``acquisition_cost`` or any inventory value — including
when the new price is below cost (FR-2.17). v1 carries stock **at cost**,
with no lower-of-cost-or-market rule: the loss on a bad buy is recognised
when the unit sells, as a thin or negative margin, not when the owner
changes the sticker.
"""

from application.dtos import CurrentUser
from application.ports import Clock, DeviceUnitPriceChangeRepository
from domain.entities import DeviceUnit, DeviceUnitPriceChange
from domain.errors import CurrencyMismatchError
from domain.value_objects import Money


class DeviceUnitRepricer:
    def __init__(
        self,
        changes: DeviceUnitPriceChangeRepository,
        clock: Clock,
        current: CurrentUser,
    ) -> None:
        self._changes = changes
        self._clock = clock
        self._current = current

    async def set_price(
        self, unit: DeviceUnit, new_price: Money, reason: str | None = None
    ) -> None:
        """Move *unit* to *new_price*, appending the row that records it.

        There is no way to reprice to ``None``: a price cannot be un-set
        (§4.5b), because the log has no row shape meaning "no longer
        priced" and the projection would then contradict its own history.

        A no-op when the price is unchanged — repricing a handset to what
        it already asks is not a markdown, and logging it would put noise
        into the ageing report's "how many times has this been cut?"
        (FR-9.4).
        """
        unit.assert_repriceable()
        if new_price.currency is not unit.currency:
            raise CurrencyMismatchError(
                f"priced in {new_price.currency.value} but IMEI {unit.imei} is "
                f"denominated in {unit.currency.value} — a unit takes its currency "
                "from its product (FR-2.13)"
            )
        if unit.asking_price == new_price:
            return

        await self._changes.add(
            DeviceUnitPriceChange(
                device_unit_id=unit.id,
                occurred_at=self._clock.now(),
                old_price=unit.asking_price,
                new_price=new_price,
                reason=reason,
                user_id=self._current.user_id,
            )
        )
        unit.asking_price = new_price
        # Re-run the entity's invariants over the new price: a negative
        # amount or a mismatched currency must fail here, not at the row.
        unit.__post_init__()
