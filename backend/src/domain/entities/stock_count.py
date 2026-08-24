"""Counting the shelf against the books (PRD §4.4, §5.6).

The only internal document: nothing enters or leaves the store, and the
adjustments exist to make the system agree with what is physically there.

**Four steps, three statuses.** A count is opened against a location and
snapshots what the books expect, is scanned, is *closed* to report its
discrepancies (FR-6.3), and is confirmed to apply them (FR-6.4). That is one
step more than ``DocumentStatus`` has values, and the fourth lives here as
``closed_at``/``closed_by`` rather than as a shared enum member — a count is
the only document with a close, and giving every Purchase Order a state it
can never enter would be the wrong trade. Closing is what freezes the three
lists so that what was reported and what is applied describe the same shelf.

**A surprise handset is always ``USED``.** FR-6.4b says it enters with no
asking price, and FR-2.14 only refuses to quote a catalog price for a unit
that is not ``NEW`` — so if the condition were an operator's choice, a
count could still produce a handset quoted at the new-goods price, which is
exactly the silent corruption §4.5b exists to prevent. Nothing about a
phone found on a shelf says it is sealed. An Owner or Manager who knows
better changes it afterwards (FR-2.18).

Every rule in ``confirm`` is a pure function of the count's own rows. What
each adjustment is *worth* needs the live unit and the replayed cost pool,
so that belongs to ``CountPoster`` — the same split ``GoodsReceipt`` keeps.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import CountOutcome
from domain.errors import (
    CountAlreadyClosedError,
    CountNotClosedError,
    EmptyDocumentError,
    InvalidLineError,
    InvalidMoneyError,
    UnpricedUnitError,
)
from domain.value_objects import IMEI, Money


@dataclass(eq=False, kw_only=True)
class StockCountUnit(UuidEntity, TenantEntity):
    """One handset the count knows about, from either direction.

    A row exists because the opening snapshot expected the handset, or
    because somebody scanned it, or both — and which of those is true is
    the whole discrepancy report.

    ``device_unit_id`` and ``product_id`` are null together, for a scan of
    an IMEI the system has no row for at all. ``acquisition_cost`` is null
    for every other row: an expected handset already carries its own cost,
    and only a genuine surprise needs one stated (FR-6.4b).
    """

    stock_count_id: UUID
    imei: IMEI
    device_unit_id: UUID | None = None
    product_id: UUID | None = None
    expected: bool
    scanned: bool = False
    acquisition_cost: Money | None = None

    def __post_init__(self) -> None:
        if not self.expected and not self.scanned:
            raise InvalidLineError(
                f"IMEI {self.imei} is neither expected nor scanned — the count has "
                "no reason to know about it"
            )
        if self.device_unit_id is None and self.expected:
            raise InvalidLineError(
                f"IMEI {self.imei} is expected by the snapshot, so it names the "
                "handset the books already hold"
            )
        if self.acquisition_cost is None:
            return
        if self.acquisition_cost.is_negative:
            raise InvalidMoneyError("an acquisition cost may not be negative")
        if self.product_id is None:
            # Not merely odd: the row stores a bare minor amount and recovers
            # its currency from the product (§4.5 rule 3), so a cost with no
            # product is a number nothing can read back.
            raise InvalidLineError(
                f"IMEI {self.imei} carries a cost but names no product — an amount "
                "is denominated by the catalog row it belongs to (§4.5 rule 3)"
            )

    @property
    def outcome(self) -> CountOutcome:
        if self.expected:
            return CountOutcome.MATCHED if self.scanned else CountOutcome.MISSING
        return CountOutcome.UNEXPECTED

    @property
    def is_surprise(self) -> bool:
        """Scanned, and the system has no handset behind it (FR-6.4b).

        The only row a confirm has to *create* a ``DeviceUnit`` for, and so
        the only one that has to be told what it cost.
        """
        return self.device_unit_id is None


@dataclass(eq=False, kw_only=True)
class StockCountLine(UuidEntity, TenantEntity):
    """One accessory the count expects a number of (FR-6.2).

    ``counted_quantity`` is null until somebody enters one, which is not the
    same as counting zero — a shelf nobody looked at and a shelf found empty
    are different findings, and confirming the first would book a loss on
    evidence that does not exist.
    """

    stock_count_id: UUID
    product_id: UUID
    expected_quantity: int
    counted_quantity: int | None = None

    def __post_init__(self) -> None:
        if self.counted_quantity is not None and self.counted_quantity < 0:
            raise InvalidLineError(
                f"a count of {self.counted_quantity} is not a number of things on a shelf"
            )

    @property
    def delta(self) -> int:
        """What the adjustment must move, or 0 while nothing has been counted."""
        if self.counted_quantity is None:
            return 0
        return self.counted_quantity - self.expected_quantity


@dataclass(eq=False, kw_only=True)
class StockCount(Document):
    location_id: UUID
    closed_at: datetime | None = None
    closed_by: UUID | None = None
    units: list[StockCountUnit] = field(default_factory=list)
    lines: list[StockCountLine] = field(default_factory=list)

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    def assert_countable(self) -> None:
        """Whether a scan or a counted quantity may still be recorded."""
        self.assert_editable()
        if self.is_closed:
            raise CountAlreadyClosedError(
                f"{self.number} was closed and its discrepancies reported — "
                "reopening it would let the adjustments describe a different shelf"
            )

    def assert_valuable(self) -> None:
        """Whether a known surprise's product/cost may still be stated (FR-6.4b).

        Unlike ``assert_countable``, this holds even after close — the
        discrepancy report is frozen, but pricing a surprise the count
        already found does not change what was found, only what it is worth.
        """
        self.assert_editable()

    def close(self, now: datetime, user_id: UUID) -> None:
        """FR-6.3: freeze the count and report matched, missing and unexpected."""
        self.assert_countable()
        self._assert_has_something_to_count()
        self.closed_at = now
        self.closed_by = user_id

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-6.4: everything that must be true before reality wins."""
        self.assert_editable()
        self._assert_closed()
        self._assert_surprises_priced()
        super().confirm(now, user_id)

    def matched(self) -> list[StockCountUnit]:
        return [u for u in self.units if u.outcome is CountOutcome.MATCHED]

    def missing(self) -> list[StockCountUnit]:
        return [u for u in self.units if u.outcome is CountOutcome.MISSING]

    def unexpected(self) -> list[StockCountUnit]:
        return [u for u in self.units if u.outcome is CountOutcome.UNEXPECTED]

    def unit_for_imei(self, imei: IMEI) -> StockCountUnit | None:
        """The row this IMEI already has — either snapshotted or scanned (§6)."""
        return next((u for u in self.units if u.imei == imei), None)

    def line_for_product(self, product_id: UUID) -> StockCountLine | None:
        return next((line for line in self.lines if line.product_id == product_id), None)

    def _assert_has_something_to_count(self) -> None:
        if not self.units and not self.lines:
            raise EmptyDocumentError(
                f"{self.number} snapshotted nothing and scanned nothing — there is "
                "no shelf here to report on"
            )

    def _assert_closed(self) -> None:
        if not self.is_closed:
            raise CountNotClosedError(
                f"{self.number} has not been closed — its discrepancies have to be "
                "reported before they are applied (FR-6.3)"
            )

    def _assert_surprises_priced(self) -> None:
        """FR-6.4b, naming every offending IMEI in one message.

        One pass rather than one handset at a time, for the same reason
        ``GoodsReceipt._assert_priced`` makes one: the person fixing this is
        standing at a shelf, and a count that reveals its gaps one error at
        a time turns that into ten round trips.
        """
        unknown = sorted(
            str(u.imei) for u in self.unexpected() if u.is_surprise and u.product_id is None
        )
        if unknown:
            raise UnpricedUnitError(
                f"{self.number} cannot be confirmed — these handsets are unknown to "
                f"the store and name no product: {', '.join(unknown)} (FR-6.3)"
            )

        costless = sorted(
            str(u.imei)
            for u in self.unexpected()
            if u.is_surprise and u.acquisition_cost is None
        )
        if costless:
            raise UnpricedUnitError(
                f"{self.number} cannot be confirmed — nothing says what these cost, "
                f"and a surplus is booked at its value: {', '.join(costless)} (FR-6.4b)"
            )
