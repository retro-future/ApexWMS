"""Goods receipts, their lines and every IMEI scanned onto them (PRD §4.4).

Three levels reassembled into one aggregate, in three queries whatever the
page size. Lines join ``products`` because a line's currency and tracking
type are the product's (§4.5 rule 3, §4.1), which is also why the entity
is rebuilt from a ``Row``.

``add_unit``/``update_unit``/``remove_unit`` exist because a scan is one
row. Rewriting the whole receipt per beep would put a fifty-line document
through the database on every trigger pull, and §6 gives the whole round
trip 200ms.

``update`` writes the header only, for the same reason the purchase-order
repository does: lines are fixed at creation, and scans have their own
three methods.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import Row, delete, select

from domain.entities import GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.enums import (
    AcquisitionSource,
    DeviceCondition,
    DocumentStatus,
    TrackingType,
)
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import (
    GoodsReceiptLineModel,
    GoodsReceiptModel,
    ProductModel,
    ReceivedUnitModel,
)

from .base import TenantRepository


class SqlGoodsReceiptRepository(TenantRepository):
    async def get(self, key: UUID) -> GoodsReceipt | None:
        row = await self._row(GoodsReceiptModel, key)
        if row is None:
            return None
        lines = await self._lines_for([key])
        return self._to_entity(row, lines[key])

    async def add(self, entity: GoodsReceipt) -> None:
        await self._insert(self._to_model(entity))
        for line in entity.lines:
            await self._insert(
                GoodsReceiptLineModel(
                    id=line.id,
                    goods_receipt_id=entity.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_cost_minor=(
                        line.unit_cost.amount_minor if line.unit_cost else None
                    ),
                )
            )
            for unit in line.units:
                await self.add_unit(unit)

    async def update(self, entity: GoodsReceipt) -> None:
        row = await self._require_row(GoodsReceiptModel, entity.id)
        # The number, the author and the source are absent on purpose:
        # none of them can change about a receipt once it has been opened.
        row.status = entity.status.value
        row.note = entity.note
        row.confirmed_by = entity.confirmed_by
        row.confirmed_at = entity.confirmed_at
        row.cancelled_by = entity.cancelled_by
        row.cancelled_at = entity.cancelled_at
        row.cancellation_reason = entity.cancellation_reason

    async def add_unit(self, unit: ReceivedUnit) -> None:
        await self._insert(
            ReceivedUnitModel(
                id=unit.id,
                goods_receipt_line_id=unit.goods_receipt_line_id,
                imei=str(unit.imei),
                imei2=str(unit.imei2) if unit.imei2 else None,
                serial_number=unit.serial_number,
                condition=unit.condition.value,
                acquisition_cost_minor=(
                    unit.acquisition_cost.amount_minor if unit.acquisition_cost else None
                ),
                asking_price_minor=(
                    unit.asking_price.amount_minor if unit.asking_price else None
                ),
                cash_paid_minor=unit.cash_paid_minor,
                cash_paid_currency=(
                    unit.cash_paid_currency.value if unit.cash_paid_currency else None
                ),
            )
        )

    async def update_unit(self, unit: ReceivedUnit) -> None:
        row = await self._require_row(ReceivedUnitModel, unit.id)
        # The IMEI is absent on purpose: a mis-scan is removed and scanned
        # again, so the operator sees the duplicate check run on the new one.
        row.condition = unit.condition.value
        row.acquisition_cost_minor = (
            unit.acquisition_cost.amount_minor if unit.acquisition_cost else None
        )
        row.asking_price_minor = (
            unit.asking_price.amount_minor if unit.asking_price else None
        )
        row.cash_paid_minor = unit.cash_paid_minor
        row.cash_paid_currency = (
            unit.cash_paid_currency.value if unit.cash_paid_currency else None
        )

    async def remove_unit(self, unit_id: UUID) -> None:
        await self._session.execute(
            delete(ReceivedUnitModel).where(ReceivedUnitModel.id == unit_id)
        )

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        acquisition_source: AcquisitionSource | None = None,
    ) -> tuple[list[GoodsReceipt], int]:
        stmt = select(GoodsReceiptModel)
        if search:
            stmt = stmt.where(GoodsReceiptModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            stmt = stmt.where(GoodsReceiptModel.status == status.value)
        if acquisition_source is not None:
            stmt = stmt.where(
                GoodsReceiptModel.acquisition_source == acquisition_source.value
            )
        stmt = stmt.order_by(GoodsReceiptModel.created_at.desc(), GoodsReceiptModel.id)

        rows, total = await self._page(stmt, page, page_size, lambda row: row)
        lines = await self._lines_for([row.id for row in rows])
        return [self._to_entity(row, lines[row.id]) for row in rows], total

    async def received_quantities(self, purchase_order_id: UUID) -> dict[UUID, int]:
        """FR-3.9's numerator: confirmed receipts only.

        A draft has received nothing — it is a shopping list, and counting
        it would report an order as complete while the goods are still on
        the van.
        """
        stmt = (
            select(GoodsReceiptLineModel.product_id, GoodsReceiptLineModel.quantity)
            .join(
                GoodsReceiptModel,
                GoodsReceiptModel.id == GoodsReceiptLineModel.goods_receipt_id,
            )
            .where(
                GoodsReceiptModel.purchase_order_id == purchase_order_id,
                GoodsReceiptModel.status == DocumentStatus.CONFIRMED.value,
            )
        )
        received: dict[UUID, int] = {}
        for product_id, quantity in await self._session.execute(stmt):
            received[product_id] = received.get(product_id, 0) + quantity
        return received

    async def supplier_of(self, receipt_id: UUID) -> UUID | None:
        stmt = select(GoodsReceiptModel.supplier_id).where(
            GoodsReceiptModel.id == receipt_id
        )
        return await self._session.scalar(stmt)

    async def _lines_for(
        self, receipt_ids: list[UUID]
    ) -> defaultdict[UUID, list[GoodsReceiptLine]]:
        lines: defaultdict[UUID, list[GoodsReceiptLine]] = defaultdict(list)
        if not receipt_ids:
            return lines

        line_stmt = (
            select(GoodsReceiptLineModel, ProductModel.currency, ProductModel.tracking_type)
            .join(ProductModel, ProductModel.id == GoodsReceiptLineModel.product_id)
            .where(GoodsReceiptLineModel.goods_receipt_id.in_(receipt_ids))
            .order_by(GoodsReceiptLineModel.product_id, GoodsReceiptLineModel.id)
        )
        by_line: dict[UUID, GoodsReceiptLine] = {}
        for row in await self._session.execute(line_stmt):
            line = self._to_line(row)
            by_line[line.id] = line
            lines[line.goods_receipt_id].append(line)

        if by_line:
            await self._attach_units(by_line)
        return lines

    async def _attach_units(self, by_line: dict[UUID, GoodsReceiptLine]) -> None:
        """Every scan on the page's lines, in the order they were scanned.

        Ordered by IMEI rather than by insertion, because a scan row has no
        sequence of its own — what matters is that the list is the same on
        every read.
        """
        stmt = (
            select(ReceivedUnitModel)
            .where(ReceivedUnitModel.goods_receipt_line_id.in_(by_line))
            .order_by(ReceivedUnitModel.imei)
        )
        for row in await self._session.scalars(stmt):
            line = by_line[row.goods_receipt_line_id]
            line.units.append(self._to_unit(row, line.currency))

    @staticmethod
    def _to_line(row: Row[tuple[GoodsReceiptLineModel, str, str]]) -> GoodsReceiptLine:
        model, currency_code, tracking_type = row._tuple()
        currency = Currency(currency_code)
        return GoodsReceiptLine(
            id=model.id,
            goods_receipt_id=model.goods_receipt_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_cost=(
                Money(model.unit_cost_minor, currency)
                if model.unit_cost_minor is not None
                else None
            ),
            tracking_type=TrackingType(tracking_type),
            currency=currency,
        )

    @staticmethod
    def _to_unit(row: ReceivedUnitModel, currency: Currency) -> ReceivedUnit:
        return ReceivedUnit(
            id=row.id,
            goods_receipt_line_id=row.goods_receipt_line_id,
            imei=IMEI(row.imei),
            imei2=IMEI(row.imei2) if row.imei2 else None,
            serial_number=row.serial_number,
            condition=DeviceCondition(row.condition),
            acquisition_cost=(
                Money(row.acquisition_cost_minor, currency)
                if row.acquisition_cost_minor is not None
                else None
            ),
            asking_price=(
                Money(row.asking_price_minor, currency)
                if row.asking_price_minor is not None
                else None
            ),
            cash_paid_minor=row.cash_paid_minor,
            cash_paid_currency=(
                Currency(row.cash_paid_currency) if row.cash_paid_currency else None
            ),
        )

    @staticmethod
    def _to_model(entity: GoodsReceipt) -> GoodsReceiptModel:
        return GoodsReceiptModel(
            id=entity.id,
            number=entity.number,
            status=entity.status.value,
            acquisition_source=entity.acquisition_source.value,
            supplier_id=entity.supplier_id,
            customer_id=entity.customer_id,
            purchase_order_id=entity.purchase_order_id,
            location_id=entity.location_id,
            note=entity.note,
            created_by=entity.created_by,
            created_at=entity.created_at,
            confirmed_by=entity.confirmed_by,
            confirmed_at=entity.confirmed_at,
            cancelled_by=entity.cancelled_by,
            cancelled_at=entity.cancelled_at,
            cancellation_reason=entity.cancellation_reason,
        )

    @staticmethod
    def _to_entity(
        row: GoodsReceiptModel, lines: list[GoodsReceiptLine]
    ) -> GoodsReceipt:
        return GoodsReceipt(
            id=row.id,
            number=row.number,
            status=DocumentStatus(row.status),
            acquisition_source=AcquisitionSource(row.acquisition_source),
            supplier_id=row.supplier_id,
            customer_id=row.customer_id,
            purchase_order_id=row.purchase_order_id,
            location_id=row.location_id,
            note=row.note,
            created_by=row.created_by,
            created_at=row.created_at,
            confirmed_by=row.confirmed_by,
            confirmed_at=row.confirmed_at,
            cancelled_by=row.cancelled_by,
            cancelled_at=row.cancelled_at,
            cancellation_reason=row.cancellation_reason,
            lines=lines,
        )
