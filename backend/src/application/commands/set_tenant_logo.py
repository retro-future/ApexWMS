"""The Owner puts the store's mark on its paperwork (FR-8.1).

Base64 in a JSON body rather than a multipart upload: the request body is
the command everywhere else in this codebase, and one image of a few dozen
kilobytes does not justify a second request-parsing path.

``content`` omitted clears the logo, so the same command both sets and
removes one.
"""

import base64
import binascii

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import TenantLogo
from application.errors import InvalidLogoError
from application.models import TenantSettingsData
from application.ports import TenantSettingsRepository, TenantUnitOfWork

_MAX_BYTES = 512 * 1024

# Sniffed rather than taken from the stated content type, which is whatever
# the client typed. PNG and JPEG only — both are what fpdf2 draws, and a
# format it cannot draw would fail at render time instead of here.
_SIGNATURES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


class SetTenantLogoCommand(Command[ResultWithData[TenantSettingsData]]):
    content: str | None = None


class SetTenantLogoHandler(
    IRequestHandler[ResultWithData[TenantSettingsData], SetTenantLogoCommand]
):
    def __init__(
        self, settings: TenantSettingsRepository, uow: TenantUnitOfWork
    ) -> None:
        self._settings = settings
        self._uow = uow

    async def handle(
        self, request: SetTenantLogoCommand
    ) -> ResultWithData[TenantSettingsData]:
        logo = None if request.content is None else self._decode(request.content)
        await self._settings.set_logo(logo)
        await self._uow.commit()
        timezone = await self._settings.get_timezone()
        letterhead = await self._settings.get_letterhead()
        return ResultWithData[TenantSettingsData].succeed_with_data(
            TenantSettingsData.from_entity(timezone, letterhead)
        )

    def _decode(self, content: str) -> TenantLogo:
        try:
            raw = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidLogoError("the logo is not valid base64") from exc
        if not raw:
            raise InvalidLogoError("the logo is empty")
        if len(raw) > _MAX_BYTES:
            raise InvalidLogoError(
                f"the logo is {len(raw)} bytes; the limit is {_MAX_BYTES}"
            )
        for signature, content_type in _SIGNATURES.items():
            if raw.startswith(signature):
                return TenantLogo(content=raw, content_type=content_type)
        raise InvalidLogoError("the logo is neither a PNG nor a JPEG")
