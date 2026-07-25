"""Application/domain error → HTTP status mapping.

Registered as FastAPI exception handlers; raised errors from use cases
(and from DI resolution, e.g. a missing bearer token) surface here.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from application.errors import (
    AlreadyMemberError,
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    InvalidSlugError,
    InvalidTimezoneError,
    InvitationError,
    LastOwnerError,
    MissingTenantError,
    NotFoundError,
    ProvisioningFailedError,
    SlugAlreadyTakenError,
    TenantNotActiveError,
    TenantNotFoundError,
)
from domain.errors import DomainError

_STATUS: list[tuple[type[Exception], int]] = [
    # Order matters: subclasses before their bases.
    (AuthenticationError, 401),
    (AuthorizationError, 403),
    (TenantNotActiveError, 403),
    (NotFoundError, 404),
    (TenantNotFoundError, 404),
    (AlreadyMemberError, 409),
    (LastOwnerError, 409),
    (SlugAlreadyTakenError, 409),
    (MissingTenantError, 400),
    (InvitationError, 400),
    (InvalidTimezoneError, 422),
    (InvalidSlugError, 422),
    (ProvisioningFailedError, 500),
    (ApplicationError, 400),
    (DomainError, 422),
]


def _status_for(exc: Exception) -> int:
    for exc_type, status in _STATUS:
        if isinstance(exc, exc_type):
            return status
    return 500


async def _handle(request: Request, exc: Exception) -> JSONResponse:
    status = _status_for(exc)
    detail = str(exc) or exc.__class__.__name__
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, _handle)
    app.add_exception_handler(DomainError, _handle)
