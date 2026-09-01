"""A handset's shelf label as a PDF (FR-8.1).

The label encodes the unit's own IMEI as Code128, so a used phone with no
box still has a scannable IMEI on the shelf. ``/scan/lookup`` and the
invoice scan both resolve an IMEI, so the label works everywhere the box
barcode would have.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import ProductLabel, RenderedDocument
from application.ports import LabelRenderer, TenantSettingsRepository
from application.services import DeviceUnitLoader
from domain.enums import LabelLayout

_MAX_COPIES = 24


class GetDeviceUnitLabelPdfQuery(Query[ResultWithData[RenderedDocument]]):
    device_unit_id: UUID
    layout: LabelLayout = LabelLayout.SINGLE
    copies: int = 1


class GetDeviceUnitLabelPdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetDeviceUnitLabelPdfQuery]
):
    def __init__(
        self,
        units: DeviceUnitLoader,
        settings: TenantSettingsRepository,
        renderer: LabelRenderer,
    ) -> None:
        self._units = units
        self._settings = settings
        self._renderer = renderer

    async def handle(
        self, request: GetDeviceUnitLabelPdfQuery
    ) -> ResultWithData[RenderedDocument]:
        unit, product = await self._units.load(request.device_unit_id)

        label = ProductLabel(
            product_name=product.name,
            code_value=str(unit.imei),
            code_symbology="code128",
        )
        content = self._renderer.render(
            label,
            await self._settings.get_letterhead(),
            request.layout,
            max(1, min(request.copies, _MAX_COPIES)),
        )
        return ResultWithData[RenderedDocument].succeed_with_data(
            RenderedDocument(
                filename=f"{unit.imei}-label.pdf",
                content_type="application/pdf",
                content=content,
            )
        )
