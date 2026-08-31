"""Query-service ports: reads that return a projection, not a whole aggregate.

A `Specification` returns whole entities, so a read that folds joined rows
into a `dict`, a DTO or a scalar does not fit one. When more than one handler
needs such a read it goes in a query service (`.claude/rules/backend/
query-services.md`); this is its port. `GoodsReceiptQueries` is the reference.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.dtos import (
    AccessoryOnHand,
    AgeingRow,
    BelowCostRow,
    CreditInvoiceDebt,
    DebtorSummary,
    FinancialLedgerRow,
    FinancingSplitRow,
    InventoryValueRow,
    MovementLogRow,
    NeedsPricingRow,
    OnHandBucket,
    PriceDeviation,
    SalesTotalsRow,
    StockGroupBy,
    UnitOrigin,
    UnitSale,
)
from application.sorting import AgeingSort, BelowCostSort, DeviationSort
from domain.enums import DocumentType, MovementType, TransactionType
from domain.value_objects import Currency, Money


class GoodsReceiptQueries(Protocol):
    async def received_quantities(self, purchase_order_id: UUID) -> dict[UUID, int]:
        """FR-3.9's numerator: how much of each product confirmed receipts
        against this order have brought in. A draft has received nothing."""
        ...

    async def supplier_of(self, receipt_id: UUID) -> UUID | None:
        """FR-5.2b asks this of one unit at a time, so it stays a column read
        rather than loading the whole receipt."""
        ...

    async def origin_of(self, receipt_id: UUID) -> UnitOrigin | None:
        """FR-9.2's first line: the supplier, or the walk-in a trade-in was
        bought from."""
        ...


class StockMovementQueries(Protocol):
    """The stock-ledger reads that return a read-model row or a scalar, not
    a ``StockMovement`` (§4.3). Every one is rebuildable from the ledger; the
    aggregate itself is the append-only generic repository."""

    async def list_page(
        self,
        page: int,
        page_size: int,
        product_id: UUID | None = None,
        location_id: UUID | None = None,
        device_unit_id: UUID | None = None,
        user_id: UUID | None = None,
        movement_type: MovementType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[MovementLogRow], int]:
        """FR-9.5: the raw ledger, newest first, with names instead of ids.
        Every filter is optional and they compose."""
        ...

    async def trace_for_unit(self, device_unit_id: UUID) -> list[MovementLogRow]:
        """FR-9.2's ledger half: one handset's movements, oldest first, in
        the joined shape ``list_page`` returns."""
        ...

    async def units_sold(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[UUID, int]:
        """FR-9.3: how many things left each shelf as a sale, net of
        cancellations (§4.3 rule 3)."""
        ...

    async def net_quantity(self, product_id: UUID, location_id: UUID) -> int:
        """The level the ledger implies for one (product, location) pair —
        the source half of ``verify-projections``."""
        ...

    async def units_on_hand(self) -> list[UUID]:
        """Every handset the ledger says the store still holds — the audit
        counterpart to the ``OnHandDeviceUnits`` spec."""
        ...

    async def moved_pairs(self, as_of: datetime | None = None) -> list[tuple[UUID, UUID]]:
        """Every (product, location) the ledger has touched, so the sweep is
        driven off the ledger and catches a level never written at all.
        *as_of* is exclusive, for the month-end close (FR-10.5)."""
        ...

    async def serialized_value_at(
        self, as_of: datetime, location_id: UUID | None = None
    ) -> list[InventoryValueRow]:
        """What the handsets on hand at *as_of* were worth, by location and
        currency — specific identification (§4.6), read from the ledger
        rather than from ``device_units.status`` so a past month can be
        valued at all. A unit is where its last movement before the cutoff
        put it."""
        ...


class DeviceUnitQueries(Protocol):
    """The two handset worklists that return read-model rows, not entities:
    what a ``Specification`` cannot express (ADR 0007). The aggregate itself
    is reached through the generic repository."""

    async def list_ageing(
        self,
        page: int,
        page_size: int,
        received_before: datetime,
        location_id: UUID | None = None,
        sort: AgeingSort = AgeingSort.AGE,
    ) -> tuple[list[AgeingRow], int]:
        """FR-9.4: on-hand handsets received before *received_before*. The
        cutoff is an instant, not a day count. ``markdown_count`` counts
        price reductions only."""
        ...

    async def list_needs_pricing(
        self,
        page: int,
        page_size: int,
        location_id: UUID | None = None,
    ) -> tuple[list[NeedsPricingRow], int]:
        """FR-9.6: on-hand handsets ``PriceResolver`` would refuse, oldest
        first — FR-2.14 read backwards, stated once in SQL."""
        ...


class StockOnHandQueries(Protocol):
    """FR-9.1's two halves, read from the two tables that hold stock. Its
    own port because the report spans both and neither aggregate owns the
    other's answer."""

    async def serialized_totals(
        self,
        group_by: StockGroupBy,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        brand: str | None = None,
    ) -> list[OnHandBucket]:
        """On-hand handsets, grouped and summed per currency — specific
        identification, so there is nothing to replay."""
        ...

    async def accessories_on_hand(
        self,
        group_by: StockGroupBy,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        brand: str | None = None,
    ) -> list[AccessoryOnHand]:
        """The accessory pairs still carrying stock, unvalued: their cost is
        a pool ``CostPoolReader`` replays, not a column to sum (§4.6)."""
        ...


class BelowCostQueries(Protocol):
    """Active accessories whose weighted-average cost has reached their
    catalog price. Its own port: the read spans ``stock_levels`` and the
    money ledger, and neither aggregate owns the other's half. The average
    is ``sum(amount_minor * INVENTORY_SIGN) / quantity`` over the pair —
    the same fold as ``services/cost_pools.py``'s ``INVENTORY_SIGN``, so
    the report and a real sale agree about the same goods."""

    async def list_below_cost(
        self,
        page: int,
        page_size: int,
        location_id: UUID | None = None,
        sort: BelowCostSort = BelowCostSort.SHORTFALL,
    ) -> tuple[list[BelowCostRow], int]: ...


class SalesInvoiceQueries(Protocol):
    """The sales-side reads that return a projection, not a ``SalesInvoice``
    (§4.4, §5.9, §5.10): the customer account, the debtor list, the total
    debt and the deviation report. None of them loads an invoice."""

    async def credit_history_for(self, customer_id: UUID) -> list[CreditInvoiceDebt]:
        """Every non-cash sale this customer has, newest first (FR-11.9).
        Cancelled invoices included: their debt is void but any payments
        still have to be surfaced for refund handling (FR-11.11)."""
        ...

    async def total_debt(self) -> Money:
        """What every customer owes the store, as one som figure (§4.7): the
        reconciliation half of ``verify-balances``."""
        ...

    async def list_deviations(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        approved_by: UUID | None = None,
        customer_id: UUID | None = None,
        sort: DeviationSort = DeviationSort.CONFIRMED_AT,
    ) -> tuple[list[PriceDeviation], int]:
        """FR-9.7: confirmed lines charged something other than the resolved
        price, newest first. Confirmed only."""
        ...

    async def sales_of_unit(self, device_unit_id: UUID) -> dict[UUID, UnitSale]:
        """Every non-draft line that sold this handset, keyed by invoice id
        so FR-9.2's trace can attach each sale to its ``SALE`` movement."""
        ...

    async def list_debtors(
        self, page: int, page_size: int
    ) -> tuple[list[DebtorSummary], int]:
        """Every customer with a balance above zero, worst-first (FR-11.10),
        ordered by the age of their oldest open invoice."""
        ...


class FinancialTransactionQueries(Protocol):
    """The money-ledger reads that group by currency and return a row or a
    dict, not a ``FinancialTransaction`` (§4.6)."""

    async def totals_by_type(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency], Money]:
        """Every category's net, per currency; *until* exclusive (FR-10.8)."""
        ...

    async def sales_totals(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> list[SalesTotalsRow]:
        """FR-9.3's ``SALE_REVENUE`` and ``COGS``, by location and currency."""
        ...

    async def list_page(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        txn_type: TransactionType | None = None,
        location_id: UUID | None = None,
        document_type: DocumentType | None = None,
    ) -> tuple[list[FinancialLedgerRow], int]:
        """FR-10.3: the raw money ledger, newest first, no total."""
        ...


class MonthEndQueries(Protocol):
    """The period reads behind the month-end close (§5.10).

    Separate from ``SalesInvoiceQueries`` because every method here asks
    about a moment or a window, not about one customer or one invoice.
    """

    async def debt_at(self, as_of: datetime) -> Money:
        """``total_debt`` at an instant (FR-10.7b): store-credit sales
        confirmed before *as_of* and not cancelled by it, less what had been
        collected. The cancellation clause is what makes a past month
        right — a sale cancelled in March was still debt in January."""
        ...

    async def debt_booked_between(self, since: datetime, until: datetime) -> Money:
        """Store-credit debt opened in the window; *until* exclusive."""
        ...

    async def debt_voided_between(self, since: datetime, until: datetime) -> Money:
        """Remaining debt on store-credit sales cancelled in the window
        (FR-11.11) — the fourth line the debt movement needs to add up."""
        ...

    async def sales_by_financing(
        self,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[FinancingSplitRow]:
        """FR-10.5's last line: invoice counts and revenue per payment type,
        credit companies named, per currency."""
        ...
