"""``verify-projections`` and ``verify-financials`` — PRD §11, FR-10.7.

A projection that *can* be rebuilt from the ledger is worth nothing until
something rebuilds it and says so. These tests do both halves: a clean
store reports nothing, and each way a projection can drift is corrupted
deliberately and caught.

The corruption is done by writing straight to a fake repository, which is
the point — it stands in for whatever future code bypasses the rules.
"""

from datetime import UTC, datetime
from uuid import uuid4

from application.dtos import MoneyEffect, Posting, PostingEntry
from application.services import LedgerReconciler, ProjectionVerifier
from domain.entities import DeviceUnit, DeviceUnitPriceChange, Product, StockLevel
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    TrackingType,
    TransactionType,
)
from domain.services import UnitProjector
from domain.value_objects import IMEI, SKU, Currency, Money
from tests.application.builders import make_world

NOW = datetime(2026, 3, 1, tzinfo=UTC)
IMEI_A = "490154203237518"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def som(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def verifier(world) -> ProjectionVerifier:
    return ProjectionVerifier(
        world.movements,
        world.levels,
        world.units,
        world.unit_price_changes,
        world.products,
        world.price_changes,
        UnitProjector(),
    )


def reconciler(world) -> LedgerReconciler:
    return LedgerReconciler(
        world.units, world.transactions, world.movements, world.cost_pools()
    )


async def accessory(world) -> Product:
    product = Product(
        sku=SKU(f"CASE-{uuid4().hex[:6].upper()}"),
        name="Clear case",
        tracking_type=TrackingType.QUANTITY,
        currency=Currency.UZS,
        is_active=True,
        created_at=NOW,
    )
    await world.products.add(product)
    return product


async def receive_accessories(world, product_id, location_id, quantity=10, unit_cost="30000"):
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
                    money=[
                        MoneyEffect(
                            TransactionType.PURCHASE, -som(unit_cost) * quantity
                        )
                    ],
                )
            ],
        )
    )


async def receive_phone(world, location_id, cost="380", imei=IMEI_A):
    product = Product(
        sku=SKU(f"IP15P-{uuid4().hex[:6].upper()}"),
        name="iPhone 15 Pro",
        tracking_type=TrackingType.SERIAL,
        currency=Currency.USD,
        is_active=True,
        created_at=NOW,
    )
    await world.products.add(product)
    unit = DeviceUnit(
        imei=IMEI(imei),
        product_id=product.id,
        status=DeviceStatus.IN_STOCK,
        location_id=location_id,
        acquisition_cost=usd(cost),
        condition=DeviceCondition.NEW,
        created_at=NOW,
    )
    await world.units.add(unit)
    await world.poster().post(
        Posting(
            document_type=DocumentType.GOODS_RECEIPT,
            document_id=uuid4(),
            entries=[
                PostingEntry(
                    movement_type=MovementType.RECEIPT,
                    product_id=product.id,
                    location_id=location_id,
                    quantity_delta=1,
                    device_unit_id=unit.id,
                    new_status=DeviceStatus.IN_STOCK,
                    new_location_id=location_id,
                    money=[MoneyEffect(TransactionType.PURCHASE, -usd(cost))],
                )
            ],
        )
    )
    return unit


class TestACleanStoreReconciles:
    async def test_an_empty_store_reports_nothing(self):
        world = make_world()

        assert await verifier(world).verify() == []
        assert await reconciler(world).reconcile() == []

    async def test_everything_written_through_the_poster_agrees(self):
        """The property the whole design rests on: goods and money posted
        together stay in step without anyone reconciling them by hand."""
        world = make_world()
        location = uuid4()
        await receive_phone(world, location)
        await receive_accessories(world, (await accessory(world)).id, location)

        assert await verifier(world).verify() == []
        assert await reconciler(world).reconcile() == []


class TestStockLevelDrift:
    async def test_a_level_edited_behind_the_ledgers_back_is_caught(self):
        world = make_world()
        product, location = uuid4(), uuid4()
        await receive_accessories(world, product, location, quantity=10)

        # Exactly what §4.3 rule 1 forbids: setting a level directly.
        level = await world.levels.get_for(product, location)
        await world.levels.update(
            StockLevel(
                id=level.id, product_id=product, location_id=location, quantity=5
            )
        )

        findings = await verifier(world).verify()
        assert len(findings) == 1
        assert (findings[0].expected, findings[0].found) == ("10", "5")

    async def test_a_movement_whose_level_was_never_written_is_caught(self):
        """Which is why the sweep is driven from the ledger and not only
        from the rows that happen to exist."""
        world = make_world()
        product, location = uuid4(), uuid4()
        await receive_accessories(world, product, location, quantity=10)
        world.levels.by_id.clear()

        findings = await verifier(world).verify()
        assert [f.found for f in findings] == ["no row"]

    async def test_a_level_invented_out_of_nothing_is_caught(self):
        world = make_world()

        await world.levels.add(
            StockLevel(product_id=uuid4(), location_id=uuid4(), quantity=7)
        )

        findings = await verifier(world).verify()
        assert [(f.expected, f.found) for f in findings] == [("0", "7")]


class TestDeviceUnitDrift:
    async def test_a_handset_moved_without_a_movement_is_caught(self):
        world = make_world()
        unit = await receive_phone(world, uuid4())

        unit.location_id = uuid4()  # "transferred", with nothing in the ledger
        await world.units.update(unit)

        findings = await verifier(world).verify()
        assert any("device unit" in f.subject for f in findings)

    async def test_a_handset_with_no_movements_at_all_is_caught(self):
        """A unit that appeared in stock without a receipt behind it —
        §4.3 rule 1's exact prohibition."""
        world = make_world()
        product = Product(
            sku=SKU("IP15P-256"),
            name="iPhone 15 Pro",
            tracking_type=TrackingType.SERIAL,
            currency=Currency.USD,
            is_active=True,
            created_at=NOW,
        )
        await world.products.add(product)
        await world.units.add(
            DeviceUnit(
                imei=IMEI(IMEI_A),
                product_id=product.id,
                status=DeviceStatus.IN_STOCK,
                location_id=uuid4(),
                acquisition_cost=usd("380"),
                condition=DeviceCondition.NEW,
                created_at=NOW,
            )
        )

        findings = await verifier(world).verify()
        assert any(f.expected == "no movements at all" for f in findings)


class TestPriceProjectionDrift:
    async def test_an_asking_price_with_no_log_row_is_caught(self):
        """§4.5b: ``asking_price`` is the latest row of the log, so a price
        that appeared without one is a projection with no source."""
        world = make_world()
        unit = await receive_phone(world, uuid4())

        unit.asking_price = usd("500")
        await world.units.update(unit)

        findings = await verifier(world).verify()
        assert any("asking price" in f.subject for f in findings)
        assert any(f.expected == "unpriced" for f in findings)

    async def test_a_price_that_does_not_match_its_last_row_is_caught(self):
        world = make_world()
        unit = await receive_phone(world, uuid4())
        await world.unit_repricer().set_price(unit, usd("500"))
        await world.units.update(unit)

        # A later log row that the projection never followed.
        await world.unit_price_changes.add(
            DeviceUnitPriceChange(
                device_unit_id=unit.id,
                occurred_at=NOW,
                old_price=usd("500"),
                new_price=usd("450"),
                user_id=uuid4(),
            )
        )

        findings = await verifier(world).verify()
        assert any(
            f.expected == "$450.00" and f.found == "$500.00" for f in findings
        )

    async def test_a_catalog_price_that_bypassed_its_log_is_caught(self):
        """FR-2.19's projection, audited the same way as the unit's."""
        world = make_world()
        product = Product(
            sku=SKU("CASE-CLEAR"),
            name="Clear case",
            tracking_type=TrackingType.QUANTITY,
            currency=Currency.UZS,
            is_active=True,
            created_at=NOW,
        )
        await world.products.add(product)

        product.default_sale_price = som("50000")
        await world.products.update(product)

        findings = await verifier(world).verify()
        assert any("catalog price" in f.subject for f in findings)


class TestFinancialReconciliation:
    async def test_on_hand_value_is_the_sum_of_what_each_unit_cost(self):
        """§4.6 specific identification — the payoff of serializing."""
        world = make_world()
        location = uuid4()
        await receive_phone(world, location, cost="380")
        await receive_phone(world, location, cost="420", imei="356938035643809")

        assert await reconciler(world).on_hand_value() == {Currency.USD: usd("800")}

    async def test_the_two_sides_agree_after_an_ordinary_receipt(self):
        world = make_world()
        await receive_phone(world, uuid4(), cost="380")

        assert await reconciler(world).ledger_value() == {Currency.USD: usd("380")}
        assert await reconciler(world).reconcile() == []

    async def test_selling_a_handset_takes_it_out_of_both_sides(self):
        """Revenue is booked and COGS removes the unit's cost — the two
        move together, which is what makes the closing figure right."""
        world = make_world()
        location = uuid4()
        unit = await receive_phone(world, location, cost="380")

        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=unit.product_id,
                        location_id=location,
                        quantity_delta=-1,
                        device_unit_id=unit.id,
                        new_status=DeviceStatus.SOLD,
                        new_location_id=None,
                        money=[
                            MoneyEffect(TransactionType.SALE_REVENUE, usd("600")),
                            MoneyEffect(TransactionType.COGS, -usd("380")),
                        ],
                    )
                ],
            )
        )

        assert await reconciler(world).on_hand_value() == {}
        assert await reconciler(world).ledger_value() == {Currency.USD: usd("0")}
        assert await reconciler(world).reconcile() == []

    async def test_revenue_never_enters_the_inventory_figure(self):
        """The sale above books $600 of revenue against a $380 unit; if
        revenue leaked into the value, the store would appear to be
        holding $220 of goods it does not have."""
        world = make_world()
        location = uuid4()
        unit = await receive_phone(world, location, cost="380")
        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=unit.product_id,
                        location_id=location,
                        quantity_delta=-1,
                        device_unit_id=unit.id,
                        new_status=DeviceStatus.SOLD,
                        new_location_id=None,
                        money=[
                            MoneyEffect(TransactionType.SALE_REVENUE, usd("600")),
                            MoneyEffect(TransactionType.COGS, -usd("380")),
                        ],
                    )
                ],
            )
        )

        value = await reconciler(world).ledger_value()
        assert value[Currency.USD].is_zero

    async def test_a_handset_added_without_a_purchase_entry_is_caught(self):
        """Goods on the shelf that the money ledger never paid for —
        FR-10.7's mismatch, surfaced rather than reconciled away."""
        world = make_world()
        product = Product(
            sku=SKU("IP15P-256"),
            name="iPhone 15 Pro",
            tracking_type=TrackingType.SERIAL,
            currency=Currency.USD,
            is_active=True,
            created_at=NOW,
        )
        await world.products.add(product)
        await world.units.add(
            DeviceUnit(
                imei=IMEI(IMEI_A),
                product_id=product.id,
                status=DeviceStatus.IN_STOCK,
                location_id=uuid4(),
                acquisition_cost=usd("380"),
                condition=DeviceCondition.NEW,
                created_at=NOW,
            )
        )

        findings = await reconciler(world).reconcile()
        assert len(findings) == 1
        assert (findings[0].expected, findings[0].found) == ("$0.00", "$380.00")

    async def test_accessories_are_valued_at_their_weighted_average(self):
        """§4.6: a box of cases has no per-unit identity, so on-hand value
        is the pool's — and the pool is rebuilt from the quantities in the
        stock ledger and the costs in the money ledger, independently of
        what the money ledger says it is holding."""
        world = make_world()
        location = uuid4()
        case = await accessory(world)
        await receive_accessories(world, case.id, location, quantity=10, unit_cost="30000")
        await receive_accessories(world, case.id, location, quantity=10, unit_cost="40000")

        assert await reconciler(world).on_hand_value() == {Currency.UZS: som("700000")}
        assert await reconciler(world).reconcile() == []

    async def test_selling_accessories_uses_the_average_at_the_time(self):
        """A sale of 5 out of a 20-unit pool averaging 35 000 so'm costs
        175 000 — and both sides still agree afterwards."""
        world = make_world()
        location = uuid4()
        case = await accessory(world)
        await receive_accessories(world, case.id, location, quantity=10, unit_cost="30000")
        await receive_accessories(world, case.id, location, quantity=10, unit_cost="40000")

        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=case.id,
                        location_id=location,
                        quantity_delta=-5,
                        money=[
                            MoneyEffect(TransactionType.SALE_REVENUE, som("250000")),
                            MoneyEffect(TransactionType.COGS, -som("175000")),
                        ],
                    )
                ],
            )
        )

        assert await reconciler(world).on_hand_value() == {Currency.UZS: som("525000")}
        assert await reconciler(world).reconcile() == []

    async def test_a_cogs_booked_at_the_wrong_average_is_caught(self):
        """The reason the pool is replayed rather than trusted: a sale that
        booked the *first* batch's price against a pool that had moved on
        leaves goods and money disagreeing, and this is what notices."""
        world = make_world()
        location = uuid4()
        case = await accessory(world)
        await receive_accessories(world, case.id, location, quantity=10, unit_cost="30000")
        await receive_accessories(world, case.id, location, quantity=10, unit_cost="40000")

        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=case.id,
                        location_id=location,
                        quantity_delta=-5,
                        money=[
                            # 30 000 × 5 — the price of the older batch, not
                            # the average the pool actually stands at.
                            MoneyEffect(TransactionType.COGS, -som("150000")),
                        ],
                    )
                ],
            )
        )

        findings = await reconciler(world).reconcile()
        assert [(f.expected, f.found) for f in findings] == [
            ("550 000 so'm", "525 000 so'm")
        ]

    async def test_a_pool_sold_out_completely_leaves_nothing_behind(self):
        """The rounding property FR-10.7 rests on, end to end: an average
        that does not divide evenly still lands both sides on zero."""
        world = make_world()
        location = uuid4()
        case = await accessory(world)
        await receive_accessories(world, case.id, location, quantity=3, unit_cost="100001")

        await world.poster().post(
            Posting(
                document_type=DocumentType.SALES_INVOICE,
                document_id=uuid4(),
                entries=[
                    PostingEntry(
                        movement_type=MovementType.SALE,
                        product_id=case.id,
                        location_id=location,
                        quantity_delta=-3,
                        money=[MoneyEffect(TransactionType.COGS, -som("300003"))],
                    )
                ],
            )
        )

        assert await reconciler(world).on_hand_value() == {}
        assert await reconciler(world).reconcile() == []

    async def test_dollars_and_som_reconcile_independently(self):
        """§4.5 rule 4 / FR-10.7: the check is per currency, so a phone
        business in dollars and an accessory business in som are two
        separate answers that are never merged."""
        world = make_world()
        location = uuid4()
        await receive_phone(world, location, cost="380")
        await receive_accessories(
            world, (await accessory(world)).id, location, quantity=10, unit_cost="30000"
        )

        assert await reconciler(world).on_hand_value() == {
            Currency.USD: usd("380"),
            Currency.UZS: som("300000"),
        }
        assert await reconciler(world).reconcile() == []

    async def test_a_cancelled_receipt_nets_the_value_back_to_zero(self):
        """FR-10.2 and FR-10.7 together: the reversal restores both sides,
        and neither ends up holding a residue."""
        world = make_world()
        location, document = uuid4(), uuid4()
        product = Product(
            sku=SKU("CASE-CLEAR"),
            name="Clear case",
            tracking_type=TrackingType.QUANTITY,
            currency=Currency.UZS,
            is_active=True,
            created_at=NOW,
        )
        await world.products.add(product)
        poster = world.poster()
        await poster.post(
            Posting(
                document_type=DocumentType.GOODS_RECEIPT,
                document_id=document,
                entries=[
                    PostingEntry(
                        movement_type=MovementType.RECEIPT,
                        product_id=product.id,
                        location_id=location,
                        quantity_delta=10,
                        money=[MoneyEffect(TransactionType.PURCHASE, -som("300000"))],
                    )
                ],
            )
        )

        await poster.reverse(DocumentType.GOODS_RECEIPT, document)

        assert await reconciler(world).ledger_value() == {Currency.UZS: som("0")}
        assert await verifier(world).verify() == []
