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
    DuplicateBarcodeError,
    DuplicateImeiError,
    DuplicateNameError,
    DuplicateSkuError,
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
from domain.errors import (
    DocumentNotConfirmedError,
    DocumentNotDraftError,
    DomainError,
    DuplicateScanError,
    InsufficientStockError,
    NotACreditSaleError,
    OverpaymentError,
    OverReceiptError,
    PaymentAlreadyReversedError,
    PriceNotSetError,
    UnitNotSellableError,
    WrongLocationError,
)

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
    (DuplicateSkuError, 409),
    (DuplicateBarcodeError, 409),
    (DuplicateNameError, 409),
    (DuplicateImeiError, 409),
    # A document in the wrong state is a conflict, not bad input: the
    # same request would have succeeded a moment earlier (§4.4).
    (DocumentNotDraftError, 409),
    (DocumentNotConfirmedError, 409),
    (OverReceiptError, 409),
    (DuplicateScanError, 409),
    # So is a handset that cannot be sold, and for the same reason: the
    # goods, not the request, are what changed (§5.4).
    (UnitNotSellableError, 409),
    (WrongLocationError, 409),
    (InsufficientStockError, 409),
    (PriceNotSetError, 409),
    # And so is a payment the balance has moved out from under: paying
    # 500 000 against a debt somebody else just cleared is a conflict, not
    # a malformed request (§4.7). Terms that contradict each other are
    # bad input, so they fall through to ``DomainError`` and 422.
    (OverpaymentError, 409),
    (NotACreditSaleError, 409),
    (PaymentAlreadyReversedError, 409),
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
