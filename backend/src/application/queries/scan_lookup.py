"""Resolve one scanned string — FR-7.1, FR-7.2, FR-7.4, PRD §6.

The operator's scanner does not know what it just read, so the client does
not either. It sends the string and this decides, in the only order that
can be right:

1. **IMEI.** A code that parses as a valid IMEI is looked up as a handset.
   ``InvalidIMEIError`` is *not* a failure here — a 13-digit barcode is a
   barcode, not a broken IMEI — so the check falls through silently.
2. **Barcode**, then **SKU**. Both identify a catalog row (§4.1: a
   quantity item has no unit to find), and a store that prints its own
   labels scans the SKU.
3. Nothing matched — ``NotFoundError``, which the error handlers turn into
   a 404. **Never an empty 200** (FR-7.4): "I do not know this code" and
   "here is nothing" read identically to a client and differently to an
   operator holding a phone.

An IMEI that parses but matches no handset does not stop the search: the
same digits could be a barcode, and refusing to look would be a guess
about what the operator scanned.
"""

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import DeviceUnitData, ProductData, ScanLookupData
from application.ports import ProductRepository
from application.services import DeviceUnitLoader
from domain.entities import DeviceUnit, Product
from domain.errors import InvalidIMEIError
from domain.permissions import Permission
from domain.value_objects import IMEI


class ScanLookupQuery(Query[ResultWithData[ScanLookupData]]):
    code: str


class ScanLookupHandler(IRequestHandler[ResultWithData[ScanLookupData], ScanLookupQuery]):
    def __init__(
        self,
        units: DeviceUnitLoader,
        products: ProductRepository,
        current: CurrentUser,
    ) -> None:
        self._units = units
        self._products = products
        self._current = current

    async def handle(self, request: ScanLookupQuery) -> ResultWithData[ScanLookupData]:
        code = request.code.strip()

        found = await self._find_device(code)
        if found is not None:
            unit, product = found
            return ResultWithData[ScanLookupData].succeed_with_data(
                ScanLookupData.for_device(
                    DeviceUnitData.from_entity(
                        unit,
                        product,
                        show_cost=Permission.COST_VIEW in self._current.permissions,
                    )
                )
            )

        product = await self._find_product(code)
        if product is not None:
            return ResultWithData[ScanLookupData].succeed_with_data(
                ScanLookupData.for_product(ProductData.from_entity(product))
            )

        raise NotFoundError(f"nothing in this store matches the code {code}")

    async def _find_device(self, code: str) -> tuple[DeviceUnit, Product] | None:
        try:
            imei = IMEI.parse(code)
        except InvalidIMEIError:
            return None
        return await self._units.load_by_imei(str(imei))

    async def _find_product(self, code: str) -> Product | None:
        # A barcode is scanned far more often than a SKU is typed, so it
        # goes first; both are unique within the store.
        by_barcode = await self._products.get_by_barcode(code)
        if by_barcode is not None:
            return by_barcode
        return await self._products.get_by_sku(code)
