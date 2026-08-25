"""The stored letterhead image, as bytes (FR-8.1).

Its own route rather than a field on the settings payload: an image in a
JSON body would be base64 on every settings read, for a value that changes
once in a store's life. ``RenderedDocument`` carries it out for the same
reason a PDF uses it — the route hands the browser raw bytes.
"""

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.errors import NotFoundError
from application.ports import TenantSettingsRepository

_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg"}


class GetTenantLogoQuery(Query[ResultWithData[RenderedDocument]]):
    pass


class GetTenantLogoHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetTenantLogoQuery]
):
    def __init__(self, settings: TenantSettingsRepository) -> None:
        self._settings = settings

    async def handle(
        self, request: GetTenantLogoQuery
    ) -> ResultWithData[RenderedDocument]:
        logo = (await self._settings.get_letterhead()).logo
        if logo is None:
            raise NotFoundError("this store has not set a letterhead logo")
        extension = _EXTENSIONS.get(logo.content_type, "bin")
        return ResultWithData[RenderedDocument].succeed_with_data(
            RenderedDocument(
                filename=f"logo.{extension}",
                content_type=logo.content_type,
                content=logo.content,
            )
        )
