"""**The M3 demo (PRD §10): a confirm writes both a stock movement and its
money entry, and both reconcile.**

M4's Goods Receipt and M5's Sales Invoice do not exist yet, so these drive
``LedgerPoster`` directly with the postings those documents will hand it.
That is the point of building the substrate first: when the receipt lands,
this is already the behaviour it inherits.

No database — the poster depends only on ports (PRD §9 Testing).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.dtos import MoneyEffect, Posting, PostingEntry
from domain.entities import DeviceUnit
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    TransactionType,
)
from domain.errors import InvalidMovementError
from domain.services import net_quantity
from domain.value_objects import IMEI, Currency, Money
from tests.application.builders import make_world

NOW = datetime(2026, 3, 1, tzinfo=UTC)
IMEI_A = "490154203237518"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def som(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


async def stocked_phone(world, location_id, **overrides) -> DeviceUnit:
    """A handset already IN_STOCK — M4's receipt in one line."""
    unit = DeviceUnit(
        imei=IMEI(IMEI_A),
        product_id=uuid4(),
        status=DeviceStatus.IN_STOCK,
        location_id=location_id,
        acquisition_cost=usd("380"),
        condition=DeviceCondition.NEW,
        created_at=NOW,
        **overrides,
    )
    await world.units.add(unit)
    return unit


def sale_of(unit, location_id, document_id, price: str = "600"):
    """The posting a Sales Invoice confirm will hand the poster: one
    handset off the shelf, revenue and COGS against it (§4.6)."""
    return Posting(
        document_type=DocumentType.SALES_INVOICE,
        document_id=document_id,
        entries=[
            PostingEntry(
                movement_type=MovementType.SALE,
                product_id=unit.product_id,
                location_id=location_id,
                quantity_delta=-1,
                device_unit_id=unit.id,
                new_status=DeviceStatus.SOLD,
                new_location_id=None,
                money=[
                    MoneyEffect(TransactionType.SALE_REVENUE, usd(price)),
                    MoneyEffect(TransactionType.COGS, -unit.acquisition_cost),
                ],
            )
        ],
    )


class TestAConfirmWritesBothLedgers:
    async def test_one_sale_writes_a_movement_and_its_money(self):
        """FR-10.1: goods and money, in the same act."""
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)

        await world.poster().post(sale_of(unit, location, document))

        assert len(world.movements.rows) == 1
        assert [t.txn_type for t in world.transactions.rows] == [
            TransactionType.SALE_REVENUE,
            TransactionType.COGS,
        ]

    async def test_both_ledgers_name_the_same_cause(self):
        """§4.3 rule 3 / §4.6 rule 3 — which is what makes "reverse
        document X" a query rather than a reconstruction."""
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)

        await world.poster().post(sale_of(unit, location, document))

        causes = {(r.document_type, r.document_id) for r in world.movements.rows} | {
            (r.document_type, r.document_id) for r in world.transactions.rows
        }
        assert causes == {(DocumentType.SALES_INVOICE, document)}

    async def test_both_ledgers_name_the_user_who_confirmed(self):
        world = make_world()
        location, document = uuid4(), uuid4()
        seller = uuid4()
        unit = await stocked_phone(world, location)

        await world.poster(seller).post(sale_of(unit, location, document))

        assert {r.user_id for r in world.movements.rows} == {seller}
        assert {r.user_id for r in world.transactions.rows} == {seller}

    async def test_goods_and_money_share_one_timestamp(self):
        """FR-10.8: a period boundary must never fall between the two
        halves of one confirm."""
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)

        await world.poster().post(sale_of(unit, location, document))

        stamps = {r.occurred_at for r in world.movements.rows} | {
            r.occurred_at for r in world.transactions.rows
        }
        assert len(stamps) == 1

    async def test_a_posting_may_move_goods_without_money(self):
        """A stock count that finds a unit exactly where it should be
        adjusts the books and moves nothing (§4.4)."""
        world = make_world()
        product, location = uuid4(), uuid4()

        await world.poster().post(
            Posting(
                document_type=DocumentType.STOCK_COUNT,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.COUNT_ADJUSTMENT,
                        product_id=product,
                        location_id=location,
                        quantity_delta=2,
                    )
                ],
            )
        )

        assert len(world.movements.rows) == 1
        assert world.transactions.rows == []


class TestProjectionsFollowTheLedger:
    async def test_a_sold_handset_leaves_the_shelf(self):
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)

        await world.poster().post(sale_of(unit, location, document))

        moved = await world.units.get(unit.id)
        assert moved.status is DeviceStatus.SOLD
        assert moved.location_id is None

    async def test_a_quantity_receipt_creates_the_level_it_needs(self):
        world = make_world()
        product, location = uuid4(), uuid4()

        await world.poster().post(
            Posting(
                document_type=DocumentType.GOODS_RECEIPT,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.RECEIPT,
                        product_id=product,
                        location_id=location,
                        quantity_delta=10,
                        money=[MoneyEffect(TransactionType.PURCHASE, -som("300000"))],
                    )
                ],
            )
        )

        level = await world.levels.get_for(product, location)
        assert level.quantity == 10

    async def test_a_second_movement_moves_the_existing_level(self):
        world = make_world()
        product, location = uuid4(), uuid4()
        poster = world.poster()

        for delta in (10, -3):
            await poster.post(
                Posting(
                    document_type=DocumentType.GOODS_RECEIPT,
                    document_id=uuid4(),
                    entries=[
                        PostingEntry(
                            movement_type=MovementType.RECEIPT,
                            product_id=product,
                            location_id=location,
                            quantity_delta=delta,
                        )
                    ],
                )
            )

        level = await world.levels.get_for(product, location)
        assert level.quantity == 7
        assert len(await world.levels.list_all()) == 1

    async def test_the_level_always_equals_what_the_ledger_says(self):
        """The invariant ``verify-projections`` exists to police."""
        world = make_world()
        product, location = uuid4(), uuid4()
        poster = world.poster()

        for delta in (10, 5, -3, -2):
            await poster.post(
                Posting(
                    document_type=DocumentType.GOODS_RECEIPT,
                    document_id=uuid4(),
                    entries=[
                        PostingEntry(
                            movement_type=MovementType.RECEIPT,
                            product_id=product,
                            location_id=location,
                            quantity_delta=delta,
                        )
                    ],
                )
            )

        level = await world.levels.get_for(product, location)
        assert level.quantity == net_quantity(world.movements.rows)

    async def test_issuing_more_than_is_held_is_refused(self):
        """FR-4.7: no partial fulfilment, and never a negative level."""
        world = make_world()
        product, location = uuid4(), uuid4()

        with pytest.raises(InvalidMovementError):
            await world.poster().post(
                Posting(
                    document_type=DocumentType.SALES_INVOICE,
                    document_id=uuid4(),
                    entries=[
                        PostingEntry(
                            movement_type=MovementType.SALE,
                            product_id=product,
                            location_id=location,
                            quantity_delta=-1,
                        )
                    ],
                )
            )


class TestCancellationCompensates:
    async def test_a_cancelled_sale_is_two_sets_of_rows_and_not_zero(self):
        """§4.3 rule 2: the history of the mistake is part of the history."""
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)
        poster = world.poster()
        await poster.post(sale_of(unit, location, document))

        await poster.reverse(DocumentType.SALES_INVOICE, document)

        assert len(world.movements.rows) == 2
        assert len(world.transactions.rows) == 4

    async def test_the_net_effect_of_a_cancelled_document_is_zero(self):
        """FR-10.2's stated test, for goods and money at once."""
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)
        poster = world.poster()
        await poster.post(sale_of(unit, location, document))

        await poster.reverse(DocumentType.SALES_INVOICE, document)

        assert net_quantity(world.movements.rows) == 0
        for currency in (Currency.USD,):
            booked = [t.amount for t in world.transactions.rows if t.currency is currency]
            assert sum(booked[1:], booked[0]) == Money.zero(currency)

    async def test_a_cancelled_sale_returns_the_handset_to_stock(self):
        """FR-4.8, and the unit lands back at the location the ledger says
        it came from — recomputed, not remembered."""
        world = make_world()
        location, document = uuid4(), uuid4()
        unit = await stocked_phone(world, location)
        # The receipt that put it there, so the timeline has an arrival to
        # restore the unit to.
        await world.poster().post(
            Posting(
                document_type=DocumentType.GOODS_RECEIPT,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.RECEIPT,
                        product_id=unit.product_id,
                        location_id=location,
                        quantity_delta=1,
                        device_unit_id=unit.id,
                        new_status=DeviceStatus.IN_STOCK,
                        new_location_id=location,
                    )
                ],
            )
        )
        poster = world.poster()
        await poster.post(sale_of(unit, location, document))

        await poster.reverse(DocumentType.SALES_INVOICE, document)

        restored = await world.units.get(unit.id)
        assert restored.status is DeviceStatus.IN_STOCK
        assert restored.location_id == location

    async def test_a_cancellation_names_the_canceller_not_the_seller(self):
        """The two need not be the same person (FR-4.5f's reasoning applied
        to the ledger): a Seller confirms, a Manager cancels."""
        world = make_world()
        location, document = uuid4(), uuid4()
        seller, manager = uuid4(), uuid4()
        unit = await stocked_phone(world, location)
        await world.poster(seller).post(sale_of(unit, location, document))

        await world.poster(manager).reverse(DocumentType.SALES_INVOICE, document)

        assert world.movements.rows[0].user_id == seller
        assert world.movements.rows[1].user_id == manager

    async def test_a_cancelled_quantity_receipt_puts_the_level_back(self):
        world = make_world()
        product, location, document = uuid4(), uuid4(), uuid4()
        poster = world.poster()
        await poster.post(
            Posting(
                document_type=DocumentType.GOODS_RECEIPT,
                document_id=document,
                entries=[
                    PostingEntry(
                        movement_type=MovementType.RECEIPT,
                        product_id=product,
                        location_id=location,
                        quantity_delta=10,
                    )
                ],
            )
        )

        await poster.reverse(DocumentType.GOODS_RECEIPT, document)

        level = await world.levels.get_for(product, location)
        assert level.quantity == 0

    async def test_reversing_one_document_leaves_another_alone(self):
        world = make_world()
        product, location = uuid4(), uuid4()
        first, second = uuid4(), uuid4()
        poster = world.poster()
        for document in (first, second):
            await poster.post(
                Posting(
                    document_type=DocumentType.GOODS_RECEIPT,
                    document_id=document,
                    entries=[
                        PostingEntry(
                            movement_type=MovementType.RECEIPT,
                            product_id=product,
                            location_id=location,
                            quantity_delta=10,
                        )
                    ],
                )
            )

        await poster.reverse(DocumentType.GOODS_RECEIPT, first)

        level = await world.levels.get_for(product, location)
        assert level.quantity == 10


async def receive(world, product_id, location_id, quantity=5):
    """Put quantity stock on the shelf, so a later sale has something to
    take off it."""
    await world.poster().post(
        Posting(
            document_type=DocumentType.GOODS_RECEIPT,
            document_id=uuid4(),
            entries=[
                PostingEntry(
                    movement_type=MovementType.RECEIPT,
                    product_id=product_id,
                    location_id=location_id,
                    quantity_delta=quantity,
                )
            ],
        )
    )


class TestMixedCurrenciesStaySeparate:
    async def test_one_document_may_book_dollars_and_som_side_by_side(self):
        """FR-2.7: a customer buying a phone and a case is one sale, and
        the ledger holds two totals that are never added together."""
        world = make_world()
        location, document = uuid4(), uuid4()
        phone, case = uuid4(), uuid4()
        await receive(world, phone, location)
        await receive(world, case, location)

        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=document,
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=phone,
                        location_id=location,
                        quantity_delta=-1,
                        money=[MoneyEffect(TransactionType.SALE_REVENUE, usd("600"))],
                    ),
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=case,
                        location_id=location,
                        quantity_delta=-1,
                        money=[MoneyEffect(TransactionType.SALE_REVENUE, som("50000"))],
                    ),
                ],
            )
        )

        totals = await world.transactions.totals_by_type()
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("600")
        assert totals[(TransactionType.SALE_REVENUE, Currency.UZS)] == som("50000")

    async def test_the_two_totals_are_never_merged(self):
        """§4.5 rule 4 / FR-2.11 — there is no key under which their sum
        could even be stored."""
        world = make_world()
        location = uuid4()
        phone, case = uuid4(), uuid4()
        await receive(world, phone, location)
        await receive(world, case, location)

        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=phone,
                        location_id=location,
                        quantity_delta=-1,
                        money=[MoneyEffect(TransactionType.SALE_REVENUE, usd("600"))],
                    ),
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=case,
                        location_id=location,
                        quantity_delta=-1,
                        money=[MoneyEffect(TransactionType.SALE_REVENUE, som("50000"))],
                    ),
                ],
            )
        )

        totals = await world.transactions.totals_by_type()
        assert {currency for _, currency in totals} == {Currency.USD, Currency.UZS}
        assert len(totals) == 2
