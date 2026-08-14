"""Purchase orders and their lines, as one aggregate (PRD §4.4).

Every read joins ``products``: a line's cost is a bare minor amount
denominated by its catalog row (§4.5 rule 3), and its tracking type is the
product's too. That is why the line is rebuilt from a ``Row`` rather than
from its own model, and so why this is not a ``TenantCrudRepository``.

``update`` writes the header only, and touches nothing about a line except
its price: ``update_line`` exists because a draft line may be raised
unpriced and priced afterward (FR-3.1). Beyond price, a line is still fixed
at creation — a wrong order is a draft to delete or a confirmed document to
cancel (§4.4), not a row to patch.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import Row, select

from domain.entities import PurchaseOrder, PurchaseOrderLine
from domain.enums import DocumentStatus, TrackingType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    ProductModel,
    PurchaseOrderLineModel,
    PurchaseOrderModel,
)

from .base import TenantRepository


class SqlPurchaseOrderRepository(TenantRepository):
    async def get(self, key: UUID) -> PurchaseOrder | None:
        row = await self._row(PurchaseOrderModel, key)
        if row is None:
            return None
        lines = await self._lines_for([key])
        return self._to_entity(row, lines[key])

    async def add(self, entity: PurchaseOrder) -> None:
        await self._insert(self._to_model(entity))
        for line in entity.lines:
            await self._insert(
                PurchaseOrderLineModel(
                    id=line.id,
                    purchase_order_id=entity.id,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_cost_minor=(
                        line.unit_cost.amount_minor if line.unit_cost else None
                    ),
                )
            )

    async def update_line(self, line: PurchaseOrderLine) -> None:
        row = await self._require_row(PurchaseOrderLineModel, line.id)
        row.unit_cost_minor = line.unit_cost.amount_minor if line.unit_cost else None

    async def update(self, entity: PurchaseOrder) -> None:
        row = await self._require_row(PurchaseOrderModel, entity.id)
        # The number and the author are absent on purpose: neither can
        # change about an order that has already been raised.
        row.status = entity.status.value
        row.supplier_id = entity.supplier_id
        row.note = entity.note
        row.confirmed_by = entity.confirmed_by
        row.confirmed_at = entity.confirmed_at
        row.cancelled_by = entity.cancelled_by
        row.cancelled_at = entity.cancelled_at
        row.cancellation_reason = entity.cancellation_reason

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        supplier_id: UUID | None = None,
    ) -> tuple[list[PurchaseOrder], int]:
        stmt = select(PurchaseOrderModel)
        if search:
            stmt = stmt.where(PurchaseOrderModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            stmt = stmt.where(PurchaseOrderModel.status == status.value)
        if supplier_id is not None:
            stmt = stmt.where(PurchaseOrderModel.supplier_id == supplier_id)
        # Newest first: the outstanding-orders screen reads the top of the
        # list, and ``id`` breaks ties so a page boundary is stable.
        stmt = stmt.order_by(
            PurchaseOrderModel.created_at.desc(), PurchaseOrderModel.id
        )

        # Paged without hydrating, then every line for the page in one
        # query: hydrating row by row would run one line query per order.
        rows, total = await self._page(stmt, page, page_size, lambda row: row)
        lines = await self._lines_for([row.id for row in rows])
        return [self._to_entity(row, lines[row.id]) for row in rows], total

    async def _lines_for(
        self, order_ids: list[UUID]
    ) -> defaultdict[UUID, list[PurchaseOrderLine]]:
        lines: defaultdict[UUID, list[PurchaseOrderLine]] = defaultdict(list)
        if not order_ids:
            return lines

        stmt = (
            select(PurchaseOrderLineModel, ProductModel.currency, ProductModel.tracking_type)
            .join(ProductModel, ProductModel.id == PurchaseOrderLineModel.product_id)
            .where(PurchaseOrderLineModel.purchase_order_id.in_(order_ids))
            # UUID keys carry no order of their own, so lines are grouped by
            # product and tie-broken by id: arbitrary, but the same on every
            # read rather than shuffling between them.
            .order_by(PurchaseOrderLineModel.product_id, PurchaseOrderLineModel.id)
        )
        for row in await self._session.execute(stmt):
            line = self._to_line(row)
            lines[line.purchase_order_id].append(line)
        return lines

    @staticmethod
    def _to_line(row: Row[tuple[PurchaseOrderLineModel, str, str]]) -> PurchaseOrderLine:
        model, currency_code, tracking_type = row._tuple()
        currency = Currency(currency_code)
        return PurchaseOrderLine(
            id=model.id,
            purchase_order_id=model.purchase_order_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_cost=(
                None
                if model.unit_cost_minor is None
                else Money(model.unit_cost_minor, currency)
            ),
            currency=currency,
            tracking_type=TrackingType(tracking_type),
        )

    @staticmethod
    def _to_model(entity: PurchaseOrder) -> PurchaseOrderModel:
        return PurchaseOrderModel(
            id=entity.id,
            number=entity.number,
            status=entity.status.value,
            supplier_id=entity.supplier_id,
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
        row: PurchaseOrderModel, lines: list[PurchaseOrderLine]
    ) -> PurchaseOrder:
        return PurchaseOrder(
            id=row.id,
            number=row.number,
            status=DocumentStatus(row.status),
            supplier_id=row.supplier_id,
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
