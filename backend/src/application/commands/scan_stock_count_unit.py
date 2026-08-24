"""FR-6.2, FR-6.3: one beep against an open count.

One endpoint, two possible answers (§6). An **IMEI** marks a handset
present; a **barcode** bumps an accessory's tally by one, because the
storekeeper walking the aisle has a scanner and nothing else, and making
them switch to a keyboard for the case shelf is the friction §6 exists to
remove. A shelf of two hundred screen protectors is typed instead, through
``PATCH /stock-counts/{id}/lines/{line_id}``.

Three things an IMEI can turn out to be, and the count records all three
without judging any of them (FR-6.3):

- one the snapshot expected — the row is marked scanned and becomes
  *matched*;
- one the store knows but did not expect here — a new *unexpected* row
  naming the handset it already has;
- one the store has never seen — a new *unexpected* row naming nothing yet.
  That is the surprise FR-6.4b is about, and it is **accepted**, not
  refused: the phone is physically on the shelf, and a count that rejected
  the very thing it exists to find would be useless.

A surprise needs a product and a cost before the count can be confirmed,
and both may be supplied here or afterwards. Neither is demanded now
because the storekeeper holding the phone may hold neither the answer nor
the pricing permission — ``StockCount.confirm()`` is the gate, and it names
every offending IMEI at once.

A repeat scan changes nothing about the count. Scanners double-fire, and
counting a phone twice would invent a handset — so §6's idempotence holds
in the sense that matters, even though a second beep may carry the product
or the cost the first one lacked.
"""

from uuid import UUID, uuid4

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import CountScanResultData
from application.ports import (
    DeviceUnitRepository,
    ProductRepository,
    StockCountRepository,
    TenantUnitOfWork,
)
from application.services import DocumentLoader
from domain.entities import Product, StockCount, StockCountLine, StockCountUnit
from domain.enums import TrackingType
from domain.errors import InvalidIMEIError
from domain.permissions import Permission
from domain.value_objects import IMEI, Money


class ScanStockCountUnitCommandPayload(CamelModel):
    # Raw scanner input: an IMEI, a barcode or a SKU (§6, FR-7.1).
    code: str
    # Only ever read for a handset the store has no row for. Naming the
    # model is identification, not pricing, so it needs no extra permission.
    product_id: UUID | None = None
    # --- pricing permission only (FR-6.4b) ---
    acquisition_cost: str | int | None = None


class ScanStockCountUnitCommand(
    ScanStockCountUnitCommandPayload, Command[ResultWithData[CountScanResultData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    stock_count_id: UUID


class ScanStockCountUnitHandler(
    IRequestHandler[ResultWithData[CountScanResultData], ScanStockCountUnitCommand]
):
    def __init__(
        self,
        counts: StockCountRepository,
        units: DeviceUnitRepository,
        products: ProductRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._units = units
        self._products = products
        self._loader = loader
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ScanStockCountUnitCommand
    ) -> ResultWithData[CountScanResultData]:
        count = await self._loader.load_count(request.stock_count_id)

        imei = self._as_imei(request.code)
        if imei is not None:
            return await self._count_handset(count, imei, request)

        count.assert_countable()
        return await self._count_accessory(count, request.code)

    async def _count_handset(
        self, count: StockCount, imei: IMEI, request: ScanStockCountUnitCommand
    ) -> ResultWithData[CountScanResultData]:
        existing = count.unit_for_imei(imei)
        if existing is not None:
            return await self._mark_present(count, existing, request)

        # Not on the count at all — a genuine new finding, which a closed
        # count can no longer record (it would change the frozen report).
        count.assert_countable()

        # Whether the *store* knows it decides whether confirming has to
        # create a handset (FR-6.4b).
        known = await self._units.get_by_imei(str(imei))
        product_id = known.product_id if known is not None else request.product_id
        row = StockCountUnit(
            id=uuid4(),
            stock_count_id=count.id,
            imei=imei,
            device_unit_id=None if known is None else known.id,
            product_id=product_id,
            expected=False,
            scanned=True,
            acquisition_cost=await self._stated_cost(request, product_id),
        )
        count.units.append(row)
        await self._counts.add_unit(row)
        await self._uow.commit()
        return self._result(count, row)

    async def _mark_present(
        self,
        count: StockCount,
        row: StockCountUnit,
        request: ScanStockCountUnitCommand,
    ) -> ResultWithData[CountScanResultData]:
        """A row this count already holds — from the snapshot or an earlier beep.

        A second beep on an already-scanned row still writes, because the
        operator may be supplying the product or the cost a surprise was
        missing. Nothing about the *count* changes, so this stays a no-op in
        the sense §6 means.

        A surprise's valuation may still change after close — that is
        pricing, not a new finding. Any other row cannot: re-affirming
        presence would edit the report the close already froze.
        """
        if row.is_surprise:
            count.assert_valuable()
        else:
            count.assert_countable()

        row.scanned = True
        if row.is_surprise:
            if request.product_id is not None:
                row.product_id = request.product_id
            cost = await self._stated_cost(request, row.product_id)
            if cost is not None:
                row.acquisition_cost = cost
        row.__post_init__()

        await self._counts.update_unit(row)
        await self._uow.commit()
        return self._result(count, row)

    async def _count_accessory(
        self, count: StockCount, code: str
    ) -> ResultWithData[CountScanResultData]:
        product = await self._as_product(code)
        if product.tracking_type is TrackingType.SERIAL:
            raise NotFoundError(
                f"{product.sku} is a serialized model, and a count records each "
                "handset — scan the phone's IMEI rather than the model's barcode"
            )

        line = count.line_for_product(product.id)
        if line is None:
            # The books have no level here at all, so the whole shelf is a
            # surplus. A line has to exist before it can be counted.
            line = StockCountLine(
                id=uuid4(),
                stock_count_id=count.id,
                product_id=product.id,
                expected_quantity=0,
                counted_quantity=0,
            )
            count.lines.append(line)
            await self._counts.add_lines([line])

        # None means nobody has counted yet, which is not zero (FR-6.2).
        line.counted_quantity = (line.counted_quantity or 0) + 1
        await self._counts.update_line(line)
        await self._uow.commit()
        return self._result(count, line)

    async def _stated_cost(
        self, request: ScanStockCountUnitCommand, product_id: UUID | None
    ) -> Money | None:
        """What the operator says a surprise cost, in its product's currency.

        The currency is the product's and never the caller's (§4.5 rule 3),
        which is why a cost cannot be stated before the model is known.
        """
        if request.acquisition_cost is None:
            return None
        if product_id is None:
            raise NotFoundError(
                "a cost is denominated by the model it belongs to (§4.5 rule 3) — "
                "name the product this handset is before pricing it"
            )
        product = await self._products.get(product_id)
        if product is None:
            raise NotFoundError(f"product {product_id} does not exist in this store")
        return Money.from_major(request.acquisition_cost, product.currency)

    @staticmethod
    def _as_imei(code: str) -> IMEI | None:
        """A scanned string is an IMEI only if it parses as one.

        ``InvalidIMEIError`` is swallowed rather than raised: a 13-digit
        barcode is not a malformed IMEI, it is a barcode, and the caller
        never said which it was sending (§6).
        """
        try:
            return IMEI.parse(code)
        except InvalidIMEIError:
            return None

    async def _as_product(self, code: str) -> Product:
        product = await self._products.get_by_barcode(code)
        if product is None:
            product = await self._products.get_by_sku(code)
        if product is None:
            raise NotFoundError(f"nothing in this store is identified by {code!r}")
        return product

    def _result(
        self, count: StockCount, found: StockCountUnit | StockCountLine
    ) -> ResultWithData[CountScanResultData]:
        return ResultWithData[CountScanResultData].succeed_with_data(
            CountScanResultData.from_entity(
                count,
                found,
                show_cost=Permission.COST_VIEW in self._current.permissions,
            )
        )
