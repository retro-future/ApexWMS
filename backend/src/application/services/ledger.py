"""Writing both ledgers, and moving what they project — PRD §4.3, §4.6.

**This is the collaborator every document confirm from M4 onward calls,
and the reason M3 exists ahead of the documents that will use it.** A
Goods Receipt, a Sales Invoice, a Write-Off and a Stock Count differ in
what they compute; they do not differ in how they record it, and letting
each work that out for itself is how two ledgers drift apart.

Three properties it exists to guarantee:

1. **Both ledgers or neither** (FR-10.1). ``post`` appends the movements,
   appends the money entries, and moves the projections — and **never
   commits**. The calling handler owns the transaction, so a failure
   anywhere rolls goods and money back together. That is why there is no
   unit of work in this constructor: a service that could commit could
   commit half of something.
2. **Nothing mutates stock except by writing a movement** (§4.3 rule 1).
   The projection updates live here, behind the movement that causes
   them, so no code path sets a level or a status on its own.
3. **Cancellation compensates, never deletes** (§4.3 rule 2, FR-10.2).
   ``reverse`` reads what a document wrote and appends the negation. Both
   sets stay visible and the pair nets to zero.

What it deliberately does *not* do is decide anything. Which units move,
what they cost, what they sold for, and whether the document was allowed
to confirm at all are the document's business — by the time a ``Posting``
arrives here, every judgement has been made.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.dtos import CurrentUser, MoneyEffect, Posting, PostingEntry
from application.ports import Clock
from application.specs import (
    DeviceUnitById,
    MovementsForDocument,
    MovementsForUnit,
    StockLevelForPair,
    TransactionsForDocument,
)
from domain.entities import DeviceUnit, FinancialTransaction, StockLevel, StockMovement
from domain.enums import DocumentType
from domain.errors import InvalidMovementError
from domain.services import UnitProjector
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    FinancialTransactionModel,
    StockLevelModel,
    StockMovementModel,
)


class LedgerPoster:
    def __init__(
        self,
        movements: TenantAppendOnlyRepository[StockMovement, StockMovementModel],
        transactions: TenantAppendOnlyRepository[
            FinancialTransaction, FinancialTransactionModel
        ],
        levels: TenantDbRepository[StockLevel, StockLevelModel],
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        clock: Clock,
        current: CurrentUser,
        projector: UnitProjector,
    ) -> None:
        self._movements = movements
        self._transactions = transactions
        self._levels = levels
        self._units = units
        self._clock = clock
        self._current = current
        self._projector = projector

    async def post(self, posting: Posting) -> None:
        """Record everything one confirmed document did.

        One timestamp for the whole posting, not one per entry: the goods
        and the money moved in the same act, and a period boundary must
        never fall between two rows of it (FR-10.8).
        """
        occurred_at = self._clock.now()
        for entry in posting.entries:
            await self._post_entry(posting, entry, occurred_at)

    async def post_money(
        self,
        document_type: DocumentType,
        document_id: UUID,
        effects: Sequence[MoneyEffect],
        *,
        location_id: UUID | None = None,
    ) -> None:
        """Record money that moved with no goods behind it (§4.7).

        ``PostingEntry`` exists so nobody can describe a stock effect
        without saying what it did to the money. A customer payment is the
        genuine inverse — cash arrives and nothing leaves the shelf — and
        there is no stock movement to hang it on. Naming that case here
        keeps every ledger write inside this one service rather than
        letting a caller reach the transaction repository directly.

        Payments are the only caller. If a second one appears that *does*
        move goods, it belongs in ``post``.
        """
        occurred_at = self._clock.now()
        for effect in effects:
            await self._transactions.add(
                FinancialTransaction(
                    occurred_at=occurred_at,
                    txn_type=effect.txn_type,
                    amount=effect.amount,
                    document_type=document_type,
                    document_id=document_id,
                    location_id=location_id,
                    user_id=self._current.user_id,
                    note=effect.note,
                )
            )

    async def reverse(self, document_type: DocumentType, document_id: UUID) -> None:
        """Compensate everything *document_id* wrote (FR-4.8, FR-10.2).

        The originals stay. A cancelled sale is *two* sets of rows — the
        sale and its reversal — not zero, because the history of the
        mistake is part of the history.

        Reversing an already-reversed document would re-apply it, so
        refusing to cancel twice belongs to the document's own
        ``CANCELLED`` state (§4.4), not here.
        """
        occurred_at = self._clock.now()
        actor = self._current.user_id

        original = await self._movements.find(MovementsForDocument(document_type, document_id))
        for movement in original:
            compensating = movement.reversed(occurred_at, actor)
            await self._movements.add(compensating)
            await self._apply_to_level(compensating)

        for transaction in await self._transactions.find(
            TransactionsForDocument(document_type, document_id)
        ):
            await self._transactions.add(transaction.reversed(occurred_at, actor))

        for unit_id in {m.device_unit_id for m in original if m.device_unit_id is not None}:
            await self._reproject_unit(unit_id)

    async def _post_entry(
        self, posting: Posting, entry: PostingEntry, occurred_at: datetime
    ) -> None:
        movement = StockMovement(
            occurred_at=occurred_at,
            movement_type=entry.movement_type,
            product_id=entry.product_id,
            device_unit_id=entry.device_unit_id,
            location_id=entry.location_id,
            quantity_delta=entry.quantity_delta,
            document_type=posting.document_type,
            document_id=posting.document_id,
            user_id=self._current.user_id,
            note=entry.note,
        )
        await self._movements.add(movement)

        for effect in entry.money:
            await self._transactions.add(
                FinancialTransaction(
                    occurred_at=occurred_at,
                    txn_type=effect.txn_type,
                    amount=effect.amount,
                    document_type=posting.document_type,
                    document_id=posting.document_id,
                    location_id=entry.location_id,
                    product_id=entry.product_id,
                    device_unit_id=entry.device_unit_id,
                    user_id=self._current.user_id,
                    note=effect.note,
                )
            )

        if entry.device_unit_id is None:
            await self._apply_to_level(movement)
        elif entry.new_status is not None:
            await self._move_unit(entry)

    async def _apply_to_level(self, movement: StockMovement) -> None:
        """Move the quantity projection behind *movement* (§4.2).

        Serialized movements never reach here: a phone's whereabouts is its
        own ``location_id``, which is this same projection at the grain its
        tracking type demands.
        """
        if movement.device_unit_id is not None:
            return

        level = await self._levels.find_one(
            StockLevelForPair(movement.product_id, movement.location_id)
        )
        if level is None:
            # Constructing validates, so an issue against a location that
            # never received anything fails here rather than persisting a
            # negative row (FR-4.7).
            await self._levels.add(
                StockLevel(
                    product_id=movement.product_id,
                    location_id=movement.location_id,
                    quantity=movement.quantity_delta,
                )
            )
            return

        await self._levels.update(
            StockLevel(
                id=level.id,
                product_id=level.product_id,
                location_id=level.location_id,
                quantity=level.quantity + movement.quantity_delta,
            )
        )

    async def _move_unit(self, entry: PostingEntry) -> None:
        """Move one handset's status and location (§4.2).

        The document states where the unit lands rather than this service
        inferring it, because only the document knows whether a ``-1``
        means sold, written off, or returned to a supplier.
        """
        assert entry.device_unit_id is not None and entry.new_status is not None

        unit = await self._units.find_one(DeviceUnitById(entry.device_unit_id))
        if unit is None:
            raise InvalidMovementError(
                f"movement names device unit {entry.device_unit_id}, which does not exist"
            )
        unit.status = entry.new_status
        unit.location_id = entry.new_location_id
        # Re-run the entity's invariants over the moved state: a unit left
        # SOLD while still holding a location, or IN_STOCK and nowhere,
        # must fail here rather than reach the row.
        unit.__post_init__()
        await self._units.update(unit)

    async def _reproject_unit(self, unit_id: UUID) -> None:
        """Put a handset back where its own timeline now says it is.

        Recomputed rather than remembered — the same rule
        ``verify-projections`` audits with (``domain/services/projection.py``),
        so a cancellation cannot leave the unit in a state the ledger
        would disagree with.
        """
        unit = await self._units.find_one(DeviceUnitById(unit_id))
        if unit is None:
            return

        status, location_id = self._projector.project(
            await self._movements.find(MovementsForUnit(unit_id))
        )
        unit.status = status
        unit.location_id = location_id
        unit.__post_init__()
        await self._units.update(unit)
