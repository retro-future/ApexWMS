"""Rebuilding every projection from its source and reporting the gaps.

The service behind ``apexwms verify-projections`` (§4.3, §4.5b): stock
levels, device statuses and both price projections, each recomputed from
the append-only rows that are supposed to imply it. A mismatch means
something wrote a projection without writing the row behind it.
"""

from application.ports import (
    DeviceUnitPriceChangeRepository,
    DeviceUnitRepository,
    ProductPriceChangeRepository,
    ProductRepository,
    StockLevelRepository,
    StockMovementRepository,
)
from application.services.verification.discrepancy import Discrepancy
from domain.entities import DeviceUnit
from domain.services import UnitProjector
from domain.value_objects import Money

# How many catalog rows a sweep pulls at a time.
_PAGE_SIZE = 200


class ProjectionVerifier:
    """Rebuilds every projection from its source and reports the gaps."""

    def __init__(
        self,
        movements: StockMovementRepository,
        levels: StockLevelRepository,
        units: DeviceUnitRepository,
        unit_prices: DeviceUnitPriceChangeRepository,
        products: ProductRepository,
        product_prices: ProductPriceChangeRepository,
        projector: UnitProjector,
    ) -> None:
        self._movements = movements
        self._levels = levels
        self._units = units
        self._unit_prices = unit_prices
        self._products = products
        self._product_prices = product_prices
        self._projector = projector

    async def verify(self) -> list[Discrepancy]:
        # Swept once and handed to both unit checks: the sweep reads every
        # on-hand handset from both ends, which is not work to do twice.
        units = await self._units_to_sweep()
        return [
            *await self._verify_levels(),
            *await self._verify_units(units),
            *await self._verify_unit_prices(units),
            *await self._verify_catalog_prices(),
        ]

    async def _verify_levels(self) -> list[Discrepancy]:
        """Every (product, location) the ledger has touched, plus every
        level that exists.

        Driven from **both** ends on purpose: sweeping only the levels
        would miss a movement whose level was never written at all, and
        sweeping only the ledger would miss a level invented out of thin
        air. Each is a different bug and both are worth catching.
        """
        pairs = set(await self._movements.list_moved_pairs())
        stored = {
            (level.product_id, level.location_id): level
            for level in await self._levels.list_all()
        }
        found: list[Discrepancy] = []

        for pair in pairs | set(stored):
            product_id, location_id = pair
            expected = await self._movements.net_quantity(product_id, location_id)
            level = stored.get(pair)
            actual = 0 if level is None else level.quantity
            if expected != actual:
                found.append(
                    Discrepancy(
                        subject=f"stock level product={product_id} location={location_id}",
                        expected=str(expected),
                        found="no row" if level is None else str(actual),
                    )
                )
        return found

    async def _units_to_sweep(self) -> list[DeviceUnit]:
        """Every handset either side thinks is in stock.

        Driven from **both** ends, like the level sweep and for the same
        reason. A unit the projection has silently marked ``SOLD`` is
        invisible from the projection side — and is the drift most worth
        catching, because the phone is still on the shelf. A store's whole
        sales history is still not replayed: units that both sides agree
        have left are skipped.
        """
        by_id = {unit.id: unit for unit in await self._units.list_on_hand()}
        for unit_id in await self._movements.list_units_on_hand():
            if unit_id not in by_id:
                unit = await self._units.get(unit_id)
                if unit is not None:
                    by_id[unit_id] = unit
        return list(by_id.values())

    async def _verify_units(self, units: list[DeviceUnit]) -> list[Discrepancy]:
        """Each handset's status and location against its own timeline."""
        found: list[Discrepancy] = []
        for unit in units:
            history = await self._movements.list_for_unit(unit.id)
            if not history:
                found.append(
                    Discrepancy(
                        subject=f"device unit {unit.imei}",
                        expected="no movements at all",
                        found=f"{unit.status.value} at {unit.location_id}",
                    )
                )
                continue
            status, location_id = self._projector.project(history)
            if (status, location_id) != (unit.status, unit.location_id):
                found.append(
                    Discrepancy(
                        subject=f"device unit {unit.imei}",
                        expected=f"{status.value} at {location_id}",
                        found=f"{unit.status.value} at {unit.location_id}",
                    )
                )
        return found

    async def _verify_unit_prices(self, units: list[DeviceUnit]) -> list[Discrepancy]:
        """``asking_price`` against the last row of the unit's price log."""
        found: list[Discrepancy] = []
        for unit in units:
            latest = await self._unit_prices.latest_for_unit(unit.id)
            expected = latest.new_price if latest else None
            if expected != unit.asking_price:
                found.append(
                    Discrepancy(
                        subject=f"asking price of {unit.imei}",
                        expected=_show(expected),
                        found=_show(unit.asking_price),
                    )
                )
        return found

    async def _verify_catalog_prices(self) -> list[Discrepancy]:
        """``default_sale_price`` against the last row of the catalog log.

        Paged rather than fetched whole: a catalog is the one table here
        that a large store could plausibly have tens of thousands of rows
        in, and a sweep that only works on small tenants is not a sweep.
        """
        found: list[Discrepancy] = []
        page = 1
        while True:
            products, total = await self._products.list_page(page, _PAGE_SIZE)
            for product in products:
                latest = await self._product_prices.latest_for_product(product.id)
                expected = latest.new_price if latest else None
                if expected != product.default_sale_price:
                    found.append(
                        Discrepancy(
                            subject=f"catalog price of {product.sku}",
                            expected=_show(expected),
                            found=_show(product.default_sale_price),
                        )
                    )
            if page * _PAGE_SIZE >= total:
                return found
            page += 1


def _show(amount: Money | None) -> str:
    return "unpriced" if amount is None else amount.format()
