"""The two handset worklists that return projection rows, not entities.

An ageing row and a needs-pricing row carry joined-in product and location
names and a computed markdown count, which a ``Specification`` cannot
express (ADR 0007). Split off the device-unit repository when the aggregate
moved to the generic repository.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, Select, func, or_, select

from application.dtos import (
    AgeingRow,
    DeviceInventoryRow,
    DeviceInventoryStatusFilter,
    NeedsPricingRow,
)
from application.sorting import AgeingSort, DeviceInventorySort
from domain.enums import DeviceCondition, DeviceStatus, DocumentType, MovementType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    DeviceUnitPriceChangeModel,
    LocationModel,
    ProductModel,
    StockMovementModel,
)
from infrastructure.types import TenantSession

ON_HAND = [status.value for status in DeviceStatus if status.is_on_hand]


class SqlDeviceUnitQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def list_needs_pricing(
        self,
        page: int,
        page_size: int,
        location_id: UUID | None = None,
    ) -> tuple[list[NeedsPricingRow], int]:
        """FR-9.6: on-hand handsets ``PriceResolver`` would refuse.

        The ``WHERE`` is FR-2.14 read backwards: no price of its own, and no
        catalog price it is allowed to inherit. Oldest first.
        """
        stmt = (
            select(
                DeviceUnitModel.id,
                DeviceUnitModel.imei,
                DeviceUnitModel.condition,
                DeviceUnitModel.location_id,
                DeviceUnitModel.created_at,
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.brand,
                LocationModel.name,
            )
            .join(ProductModel, ProductModel.id == DeviceUnitModel.product_id)
            .outerjoin(LocationModel, LocationModel.id == DeviceUnitModel.location_id)
            .where(
                DeviceUnitModel.status.in_(ON_HAND),
                DeviceUnitModel.asking_price_minor.is_(None),
                or_(
                    DeviceUnitModel.condition != DeviceCondition.NEW.value,
                    ProductModel.default_sale_price_minor.is_(None),
                ),
            )
        )
        if location_id is not None:
            stmt = stmt.where(DeviceUnitModel.location_id == location_id)
        stmt = stmt.order_by(DeviceUnitModel.created_at, DeviceUnitModel.id)

        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_needs_pricing(row) for row in rows], total

    async def list_ageing(
        self,
        page: int,
        page_size: int,
        received_before: datetime,
        location_id: UUID | None = None,
        sort: AgeingSort = AgeingSort.AGE,
    ) -> tuple[list[AgeingRow], int]:
        """FR-9.4: what is still on the shelf, and how hard it has been pushed.

        ``markdown_count`` counts reductions only. The first pricing has a
        null old price; a raise is not a markdown either.
        """
        markdowns = (
            select(func.count(DeviceUnitPriceChangeModel.id))
            .where(
                DeviceUnitPriceChangeModel.device_unit_id == DeviceUnitModel.id,
                DeviceUnitPriceChangeModel.old_price_minor.is_not(None),
                DeviceUnitPriceChangeModel.new_price_minor
                < DeviceUnitPriceChangeModel.old_price_minor,
            )
            .scalar_subquery()
        )
        stmt = (
            select(
                DeviceUnitModel.id,
                DeviceUnitModel.imei,
                DeviceUnitModel.condition,
                DeviceUnitModel.location_id,
                DeviceUnitModel.created_at,
                DeviceUnitModel.acquisition_cost_minor,
                DeviceUnitModel.asking_price_minor,
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.brand,
                ProductModel.currency,
                LocationModel.name,
                markdowns,
            )
            .join(ProductModel, ProductModel.id == DeviceUnitModel.product_id)
            .outerjoin(LocationModel, LocationModel.id == DeviceUnitModel.location_id)
            .where(
                DeviceUnitModel.status.in_(ON_HAND),
                DeviceUnitModel.created_at <= received_before,
            )
        )
        if location_id is not None:
            stmt = stmt.where(DeviceUnitModel.location_id == location_id)
        if sort is AgeingSort.MARKDOWNS:
            stmt = stmt.order_by(markdowns.desc(), DeviceUnitModel.created_at)
        else:
            stmt = stmt.order_by(DeviceUnitModel.created_at)
        stmt = stmt.order_by(DeviceUnitModel.id)

        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_ageing(row) for row in rows], total

    async def list_inventory(
        self,
        page: int,
        page_size: int,
        product_id: UUID | None = None,
        product_search: str | None = None,
        location_id: UUID | None = None,
        condition: DeviceCondition | None = None,
        status: DeviceInventoryStatusFilter | None = None,
        sort: DeviceInventorySort = DeviceInventorySort.RECEIVED,
    ) -> tuple[list[DeviceInventoryRow], int]:
        """FR-9.1 at the unit level: every handset, filterable, one row each.

        ``was_returned`` and the ``CUSTOMER_RETURNED`` filter both read the
        presence of a ``CUSTOMER_RETURN`` movement, because such a unit is
        ``IN_STOCK`` again and no status records that it came back.
        """
        returned = (
            select(StockMovementModel.id)
            .where(
                StockMovementModel.device_unit_id == DeviceUnitModel.id,
                StockMovementModel.movement_type == MovementType.CUSTOMER_RETURN.value,
            )
            .exists()
        )
        stmt = (
            select(
                DeviceUnitModel.id,
                DeviceUnitModel.imei,
                DeviceUnitModel.imei2,
                DeviceUnitModel.serial_number,
                DeviceUnitModel.condition,
                DeviceUnitModel.status,
                DeviceUnitModel.location_id,
                DeviceUnitModel.created_at,
                DeviceUnitModel.acquisition_cost_minor,
                DeviceUnitModel.asking_price_minor,
                DeviceUnitModel.source_document_type,
                DeviceUnitModel.source_document_id,
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.brand,
                ProductModel.currency,
                ProductModel.default_sale_price_minor,
                LocationModel.name,
                returned,
            )
            .join(ProductModel, ProductModel.id == DeviceUnitModel.product_id)
            .outerjoin(LocationModel, LocationModel.id == DeviceUnitModel.location_id)
        )
        if product_id is not None:
            stmt = stmt.where(DeviceUnitModel.product_id == product_id)
        if product_search:
            term = f"%{product_search.strip()}%"
            stmt = stmt.where(
                or_(
                    ProductModel.name.ilike(term),
                    ProductModel.sku.ilike(term),
                    ProductModel.brand.ilike(term),
                )
            )
        if location_id is not None:
            stmt = stmt.where(DeviceUnitModel.location_id == location_id)
        if condition is not None:
            stmt = stmt.where(DeviceUnitModel.condition == condition.value)
        if status is DeviceInventoryStatusFilter.CUSTOMER_RETURNED:
            stmt = stmt.where(returned)
        elif status is not None:
            stmt = stmt.where(DeviceUnitModel.status == status.value)

        if sort is DeviceInventorySort.IMEI:
            stmt = stmt.order_by(DeviceUnitModel.imei)
        elif sort is DeviceInventorySort.STATUS:
            stmt = stmt.order_by(DeviceUnitModel.status, DeviceUnitModel.created_at)
        else:
            stmt = stmt.order_by(DeviceUnitModel.created_at)
        stmt = stmt.order_by(DeviceUnitModel.id)

        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_inventory(row) for row in rows], total

    async def _count(self, stmt: Select[Any]) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        return total or 0

    @staticmethod
    def _to_needs_pricing(
        row: Row[
            tuple[UUID, str, str, UUID | None, datetime, UUID, str, str, str | None, str]
        ],
    ) -> NeedsPricingRow:
        (
            unit_id,
            imei,
            condition,
            location_id,
            created_at,
            product_id,
            sku,
            product_name,
            brand,
            location_name,
        ) = row._tuple()
        return NeedsPricingRow(
            device_unit_id=unit_id,
            imei=imei,
            product_id=product_id,
            sku=sku,
            product_name=product_name,
            brand=brand,
            condition=DeviceCondition(condition),
            location_id=location_id,
            location_name=location_name,
            created_at=created_at,
        )

    @staticmethod
    def _to_ageing(
        row: Row[
            tuple[
                UUID,
                str,
                str,
                UUID | None,
                datetime,
                int,
                int | None,
                UUID,
                str,
                str,
                str | None,
                str,
                str,
                int,
            ]
        ],
    ) -> AgeingRow:
        (
            unit_id,
            imei,
            condition,
            location_id,
            created_at,
            cost_minor,
            asking_minor,
            product_id,
            sku,
            product_name,
            brand,
            currency_code,
            location_name,
            markdown_count,
        ) = row._tuple()
        currency = Currency(currency_code)
        return AgeingRow(
            device_unit_id=unit_id,
            imei=imei,
            product_id=product_id,
            sku=sku,
            product_name=product_name,
            brand=brand,
            condition=DeviceCondition(condition),
            location_id=location_id,
            location_name=location_name,
            created_at=created_at,
            acquisition_cost=Money(cost_minor, currency),
            asking_price=(
                Money(asking_minor, currency) if asking_minor is not None else None
            ),
            markdown_count=markdown_count,
        )

    @staticmethod
    def _to_inventory(
        row: Row[
            tuple[
                UUID,
                str,
                str | None,
                str | None,
                str,
                str,
                UUID | None,
                datetime,
                int,
                int | None,
                str | None,
                UUID | None,
                UUID,
                str,
                str,
                str | None,
                str,
                int | None,
                str | None,
                bool,
            ]
        ],
    ) -> DeviceInventoryRow:
        (
            unit_id,
            imei,
            imei2,
            serial_number,
            condition,
            status,
            location_id,
            created_at,
            cost_minor,
            asking_minor,
            source_type,
            source_id,
            product_id,
            sku,
            product_name,
            brand,
            currency_code,
            catalog_minor,
            location_name,
            was_returned,
        ) = row._tuple()
        currency = Currency(currency_code)
        return DeviceInventoryRow(
            device_unit_id=unit_id,
            imei=imei,
            imei2=imei2,
            serial_number=serial_number,
            product_id=product_id,
            sku=sku,
            product_name=product_name,
            brand=brand,
            condition=DeviceCondition(condition),
            status=DeviceStatus(status),
            was_customer_returned=was_returned,
            location_id=location_id,
            location_name=location_name,
            created_at=created_at,
            acquisition_cost=Money(cost_minor, currency),
            asking_price=(
                Money(asking_minor, currency) if asking_minor is not None else None
            ),
            catalog_price=(
                Money(catalog_minor, currency) if catalog_minor is not None else None
            ),
            source_document_type=(
                DocumentType(source_type) if source_type is not None else None
            ),
            source_document_id=source_id,
        )
