"""Supplier returns and write-offs end to end through the handlers — PRD §5.5, §5.6.

No database: the whole flow runs against the in-memory fakes. What these
cover that the domain tests cannot is everything needing a lookup — that
the goods are still on the shelf, what they are carried at, and the two
ledgers.

The pair is tested together because ``RemovalPoster`` serves both, and the
thing most worth pinning down is that it labels their money differently:
a return credits the store, a write-off costs it, and reading either sign
backwards would put a loss in the profit column of §5.10's report.
"""

from uuid import uuid4

import pytest

from application.commands.cancel_supplier_return import CancelSupplierReturnCommand
from application.commands.cancel_write_off import CancelWriteOffCommand
from application.commands.confirm_supplier_return import ConfirmSupplierReturnCommand
from application.commands.confirm_write_off import ConfirmWriteOffCommand
from application.commands.create_supplier_return import CreateSupplierReturnCommand
from application.commands.create_write_off import CreateWriteOffCommand
from application.commands.scan_supplier_return_line import ScanSupplierReturnLineCommand
from application.commands.scan_write_off_line import ScanWriteOffLineCommand
from application.commands.unscan_write_off_line import UnscanWriteOffLineCommand
from domain.entities import Supplier
from domain.enums import (
    DeviceStatus,
    DocumentStatus,
    DocumentType,
    MovementType,
    SupplierReturnReason,
    TrackingType,
    TransactionType,
    WriteOffReason,
)
from domain.errors import (
    InsufficientStockError,
    UnitNotRemovableError,
    WrongLocationError,
)
from domain.value_objects import Currency, Money
from tests.application.builders import World, make_world
from tests.application.test_sales_invoice import (
    CASE_BARCODE,
    OTHER_IMEI,
    PHONE_IMEI,
    a_place,
    catalogued,
    in_stock,
    stocked_accessory,
    usd,
    uzs,
)


def a_supplier(world: World) -> Supplier:
    supplier = Supplier(name="Shenzhen Wholesale", is_active=True, created_at=world.clock.now())
    world.suppliers.by_id[supplier.id] = supplier
    return supplier


async def opened_return(world: World, location, supplier, **overrides):
    result = await world.create_supplier_return().handle(
        CreateSupplierReturnCommand(
            supplier_id=supplier.id,
            location_id=location.id,
            reason=SupplierReturnReason.DEFECTIVE,
            **overrides,
        )
    )
    assert result.data is not None
    document = await world.returns.get(result.data.id)
    assert document is not None
    return document


async def opened_write_off(world: World, location, **overrides):
    result = await world.create_write_off().handle(
        CreateWriteOffCommand(
            location_id=location.id, reason=WriteOffReason.DAMAGE, **overrides
        )
    )
    assert result.data is not None
    document = await world.write_offs.get(result.data.id)
    assert document is not None
    return document


async def scan_return(world: World, document, code: str):
    return await world.scan_supplier_return_line().handle(
        ScanSupplierReturnLineCommand(code=code, supplier_return_id=document.id)
    )


async def scan_write_off(world: World, document, code: str):
    return await world.scan_write_off_line().handle(
        ScanWriteOffLineCommand(code=code, write_off_id=document.id)
    )


def entries_for(world: World, document_type: DocumentType, document_id):
    return [
        m
        for m in world.movements.rows
        if m.document_type is document_type and m.document_id == document_id
    ]


def money_for(world: World, document_type: DocumentType, document_id):
    return [
        t
        for t in world.transactions.rows
        if t.document_type is document_type and t.document_id == document_id
    ]


class TestSendingAHandsetBack:
    async def test_the_handset_leaves_and_holds_no_location(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location, cost="380")
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)

        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=document.id)
        )

        moved = await world.units.get(unit.id)
        assert moved is not None
        assert moved.status is DeviceStatus.RETURNED_TO_SUPPLIER
        assert moved.location_id is None

    async def test_one_movement_out_at_the_units_own_cost(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, cost="380")
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)

        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=document.id)
        )

        moves = entries_for(world, DocumentType.SUPPLIER_RETURN, document.id)
        assert [m.movement_type for m in moves] == [MovementType.SUPPLIER_RETURN]
        assert [m.quantity_delta for m in moves] == [-1]

    async def test_the_credit_is_positive_and_is_the_book_value(self):
        """§4.6: a return credit brings money back, so it is booked ``+``."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, cost="380")
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)

        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=document.id)
        )

        booked = money_for(world, DocumentType.SUPPLIER_RETURN, document.id)
        assert [t.txn_type for t in booked] == [TransactionType.SUPPLIER_RETURN_CREDIT]
        assert booked[0].amount == usd("380")

    async def test_an_accessory_line_is_credited_at_its_weighted_average(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, CASE_BARCODE)
        await scan_return(world, document, CASE_BARCODE)

        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=document.id)
        )

        booked = money_for(world, DocumentType.SUPPLIER_RETURN, document.id)
        # Two of ten, from a pool of 300 000 som.
        assert booked[0].amount == uzs("60000")


class TestOnlyStockOnTheShelfMayGoBack:
    """FR-5.2, refused on the scan that named it (§6)."""

    async def test_a_sold_handset_is_refused_at_the_scan(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        unit.status = DeviceStatus.SOLD
        unit.location_id = None
        document = await opened_return(world, location, a_supplier(world))

        with pytest.raises(UnitNotRemovableError, match="sold"):
            await scan_return(world, document, PHONE_IMEI)

    async def test_a_handset_held_elsewhere_is_refused(self):
        world = make_world()
        here = a_place(world, "Shop")
        there = a_place(world, "Stockroom")
        product = catalogued(world)
        await in_stock(world, product, there)
        document = await opened_return(world, here, a_supplier(world))

        with pytest.raises(WrongLocationError):
            await scan_return(world, document, PHONE_IMEI)

    async def test_a_handset_sold_from_under_the_draft_fails_the_confirm(self):
        """A draft reserves nothing, so the scan's check is not the one that
        holds — this is."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)

        unit.status = DeviceStatus.SOLD
        unit.location_id = None

        with pytest.raises(UnitNotRemovableError):
            await world.confirm_supplier_return().handle(
                ConfirmSupplierReturnCommand(supplier_return_id=document.id)
            )

    async def test_that_failure_writes_nothing_to_either_ledger(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)
        unit.status = DeviceStatus.SOLD
        unit.location_id = None

        with pytest.raises(UnitNotRemovableError):
            await world.confirm_supplier_return().handle(
                ConfirmSupplierReturnCommand(supplier_return_id=document.id)
            )

        assert entries_for(world, DocumentType.SUPPLIER_RETURN, document.id) == []
        assert money_for(world, DocumentType.SUPPLIER_RETURN, document.id) == []

    async def test_more_accessories_than_are_here_is_refused_whole(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 1, uzs("30000"))
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, CASE_BARCODE)
        await scan_return(world, document, CASE_BARCODE)

        with pytest.raises(InsufficientStockError):
            await world.confirm_supplier_return().handle(
                ConfirmSupplierReturnCommand(supplier_return_id=document.id)
            )


class TestScanningARemoval:
    async def test_a_repeat_imei_is_a_no_op(self):
        """Scanners double-fire, and one phone is one line (§6)."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        document = await opened_return(world, location, a_supplier(world))

        await scan_return(world, document, PHONE_IMEI)
        result = await scan_return(world, document, PHONE_IMEI)

        assert result.data is not None
        assert result.data.line_count == 1

    async def test_a_repeat_barcode_increments(self):
        """Three broken cases are three items, not one."""
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        document = await opened_write_off(world, location)

        await scan_write_off(world, document, CASE_BARCODE)
        result = await scan_write_off(world, document, CASE_BARCODE)

        assert result.data is not None
        assert result.data.line_count == 1
        assert result.data.lines[0].quantity == 2

    async def test_a_serialized_model_scanned_by_sku_is_refused(self):
        world = make_world()
        location = a_place(world)
        catalogued(world, sku="IP15P-256")
        document = await opened_write_off(world, location)

        with pytest.raises(UnitNotRemovableError, match="scan the phone's IMEI"):
            await scan_write_off(world, document, "IP15P-256")

    async def test_a_line_comes_off_a_draft_with_no_trace(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)

        await world.unscan_write_off_line().handle(
            UnscanWriteOffLineCommand(write_off_id=document.id, imei=PHONE_IMEI)
        )

        reloaded = await world.write_offs.get(document.id)
        assert reloaded is not None
        assert reloaded.lines == []


class TestWritingStockOff:
    async def test_the_handset_is_written_off_and_the_loss_is_negative(self):
        """§4.6: a write-off takes value out, so it is booked ``−``."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location, cost="380")
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)

        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )

        moved = await world.units.get(unit.id)
        assert moved is not None
        assert moved.status is DeviceStatus.WRITTEN_OFF

        booked = money_for(world, DocumentType.WRITE_OFF, document.id)
        assert [t.txn_type for t in booked] == [TransactionType.WRITE_OFF_LOSS]
        assert booked[0].amount == -usd("380")

    async def test_the_movement_names_the_write_off_and_not_a_sale(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)

        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )

        moves = entries_for(world, DocumentType.WRITE_OFF, document.id)
        assert [m.movement_type for m in moves] == [MovementType.WRITE_OFF]

    async def test_no_revenue_is_booked_for_goods_that_were_not_sold(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)

        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )

        categories = {t.txn_type for t in world.transactions.rows}
        assert TransactionType.SALE_REVENUE not in categories
        assert TransactionType.COGS not in categories


class TestCancellingCompensates:
    async def test_a_returned_handset_comes_back_to_the_shelf_it_left(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)
        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=document.id)
        )

        await world.cancel_supplier_return().handle(
            CancelSupplierReturnCommand(supplier_return_id=document.id)
        )

        back = await world.units.get(unit.id)
        assert back is not None
        assert back.status is DeviceStatus.IN_STOCK
        assert back.location_id == location.id

    async def test_a_handset_written_off_and_then_found_comes_back(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)
        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )

        await world.cancel_write_off().handle(
            CancelWriteOffCommand(write_off_id=document.id, reason="found behind the desk")
        )

        back = await world.units.get(unit.id)
        assert back is not None
        assert back.status is DeviceStatus.IN_STOCK

    async def test_the_original_rows_stay_and_their_negation_is_appended(self):
        """§4.3 rule 2: a cancelled write-off is two sets of rows, not zero."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, cost="380")
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)
        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )

        await world.cancel_write_off().handle(CancelWriteOffCommand(write_off_id=document.id))

        moves = entries_for(world, DocumentType.WRITE_OFF, document.id)
        booked = money_for(world, DocumentType.WRITE_OFF, document.id)
        assert len(moves) == 2
        assert sum(m.quantity_delta for m in moves) == 0
        assert len(booked) == 2
        net = booked[0].amount + booked[1].amount
        assert net == Money.zero(Currency.USD)

    async def test_a_cancelled_write_off_frees_the_handset_to_be_sold(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        unit = await in_stock(world, product, location)
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)
        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )
        await world.cancel_write_off().handle(CancelWriteOffCommand(write_off_id=document.id))

        second = await opened_write_off(world, location)
        result = await scan_write_off(world, second, PHONE_IMEI)

        assert result.data is not None
        assert result.data.line_count == 1
        assert unit.status is DeviceStatus.IN_STOCK


class TestTheDocumentsAreNotInterchangeable:
    """§5.10 reads returns and write-offs in different columns, so the two
    must never share a category."""

    async def test_a_return_never_books_a_write_off_loss(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        document = await opened_return(world, location, a_supplier(world))
        await scan_return(world, document, PHONE_IMEI)

        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=document.id)
        )

        categories = {t.txn_type for t in world.transactions.rows}
        assert TransactionType.WRITE_OFF_LOSS not in categories

    async def test_a_write_off_never_books_a_return_credit(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        document = await opened_write_off(world, location)
        await scan_write_off(world, document, PHONE_IMEI)

        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=document.id)
        )

        categories = {t.txn_type for t in world.transactions.rows}
        assert TransactionType.SUPPLIER_RETURN_CREDIT not in categories

    async def test_the_two_land_in_different_terminal_statuses(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        returned = await in_stock(world, product, location, imei=PHONE_IMEI)
        scrapped = await in_stock(world, product, location, imei=OTHER_IMEI)

        first = await opened_return(world, location, a_supplier(world))
        await scan_return(world, first, PHONE_IMEI)
        await world.confirm_supplier_return().handle(
            ConfirmSupplierReturnCommand(supplier_return_id=first.id)
        )

        second = await opened_write_off(world, location)
        await scan_write_off(world, second, OTHER_IMEI)
        await world.confirm_write_off().handle(
            ConfirmWriteOffCommand(write_off_id=second.id)
        )

        assert returned.status is DeviceStatus.RETURNED_TO_SUPPLIER
        assert scrapped.status is DeviceStatus.WRITTEN_OFF


class TestTheDocumentsAreNumberedAndDrafted:
    async def test_a_return_opens_as_a_draft_with_its_own_number(self):
        world = make_world()
        document = await opened_return(world, a_place(world), a_supplier(world))

        assert document.status is DocumentStatus.DRAFT
        assert document.number.startswith("SR-")
        assert document.lines == []

    async def test_a_write_off_opens_as_a_draft_with_its_own_number(self):
        world = make_world()
        document = await opened_write_off(world, a_place(world))

        assert document.status is DocumentStatus.DRAFT
        assert document.number.startswith("WO-")

    async def test_a_return_names_a_location_that_exists(self):
        world = make_world()
        supplier = a_supplier(world)

        from application.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await world.create_supplier_return().handle(
                CreateSupplierReturnCommand(
                    supplier_id=supplier.id,
                    location_id=uuid4(),
                    reason=SupplierReturnReason.UNSOLD,
                )
            )
